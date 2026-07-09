import importlib

import pytest

from constrainai.constraints import Constraint, ConstraintKind, ConstraintStatus, Operator
from constrainai.expressions import add, const, var
from constrainai.store import ConstraintStore


def _fresh_persistence_module():
    """
    persistence.py caches a process-wide engine/sessionmaker keyed by db
    path; reimporting isn't necessary since get_engine() already re-creates
    the engine when the path changes, but we import fresh per test module
    load to keep this file self-contained and explicit about what's cached.
    """
    import constrainai.persistence as persistence
    return persistence


def bound(lhs, op, rhs, turn, text):
    return Constraint(
        kind=ConstraintKind.BOUND, lhs=lhs, operator=op, rhs=rhs,
        source_turn=turn, source_text=text,
    )


def test_save_and_load_round_trip(tmp_path):
    persistence = _fresh_persistence_module()
    db_path = str(tmp_path / "test1.db")

    store = ConstraintStore()
    store.add(bound(var("budget"), Operator.LE, const(20000), 1, "Budget must stay under 20k"))
    store.add(bound(
        var("gpu_cost"), Operator.GE, const(14000), 2, "GPU costs at least 14k",
    ))

    session = persistence.get_session(db_path)
    persistence.save_store(session, "conv-1", store)
    session.close()

    session2 = persistence.get_session(db_path)
    loaded = persistence.load_store(session2, "conv-1")
    session2.close()

    assert len(loaded.all()) == 2
    ids = {c.id for c in loaded.all()}
    assert ids == {c.id for c in store.all()}

    loaded_budget = loaded.get(store.all()[0].id)
    assert loaded_budget.lhs.name == "budget"
    assert loaded_budget.rhs.value == 20000
    assert loaded_budget.operator == Operator.LE
    assert loaded_budget.status == ConstraintStatus.ACTIVE


def test_round_trip_preserves_relation_expression_tree(tmp_path):
    persistence = _fresh_persistence_module()
    db_path = str(tmp_path / "test2.db")

    store = ConstraintStore()
    relation = Constraint(
        kind=ConstraintKind.RELATION,
        lhs=add(var("gpu_cost"), var("ram_cost"), var("storage_cost")),
        operator=Operator.LE, rhs=var("budget"),
        source_turn=5, source_text="gpu + ram + storage <= budget",
    )
    store.add(relation)

    session = persistence.get_session(db_path)
    persistence.save_store(session, "conv-2", store)
    session.close()

    session2 = persistence.get_session(db_path)
    loaded = persistence.load_store(session2, "conv-2")
    session2.close()

    loaded_relation = loaded.get(relation.id)
    assert loaded_relation.variables() == {"gpu_cost", "ram_cost", "storage_cost", "budget"}
    assert str(loaded_relation.lhs) == "gpu_cost + ram_cost + storage_cost"


def test_status_transitions_persist(tmp_path):
    persistence = _fresh_persistence_module()
    db_path = str(tmp_path / "test3.db")

    store = ConstraintStore()
    c = bound(var("ram_cost"), Operator.GE, const(8000), 3, "RAM costs at least 8k")
    store.add(c)
    store.retract(c.id)

    session = persistence.get_session(db_path)
    persistence.save_store(session, "conv-3", store)
    session.close()

    session2 = persistence.get_session(db_path)
    loaded = persistence.load_store(session2, "conv-3")
    session2.close()

    assert loaded.get(c.id).status == ConstraintStatus.RETRACTED
    assert loaded.active() == []


def test_conversations_are_isolated(tmp_path):
    persistence = _fresh_persistence_module()
    db_path = str(tmp_path / "test4.db")

    store_a = ConstraintStore()
    store_a.add(bound(var("budget"), Operator.LE, const(20000), 1, "conv A budget"))

    store_b = ConstraintStore()
    store_b.add(bound(var("budget"), Operator.LE, const(99999), 1, "conv B budget"))

    session = persistence.get_session(db_path)
    persistence.save_store(session, "conv-a", store_a)
    persistence.save_store(session, "conv-b", store_b)
    session.close()

    session2 = persistence.get_session(db_path)
    loaded_a = persistence.load_store(session2, "conv-a")
    loaded_b = persistence.load_store(session2, "conv-b")
    ids = persistence.list_conversation_ids(session2)
    session2.close()

    assert loaded_a.all()[0].source_text == "conv A budget"
    assert loaded_b.all()[0].source_text == "conv B budget"
    assert set(ids) == {"conv-a", "conv-b"}


def test_delete_conversation_removes_its_rows(tmp_path):
    persistence = _fresh_persistence_module()
    db_path = str(tmp_path / "test5.db")

    store = ConstraintStore()
    store.add(bound(var("budget"), Operator.LE, const(20000), 1, "budget <= 20000"))

    session = persistence.get_session(db_path)
    persistence.save_store(session, "conv-5", store)
    persistence.delete_conversation(session, "conv-5")
    session.close()

    session2 = persistence.get_session(db_path)
    loaded = persistence.load_store(session2, "conv-5")
    session2.close()
    assert loaded.all() == []


def test_id_counter_survives_simulated_process_restart(tmp_path):
    """
    Simulates a process restart: constraints are created (consuming ids
    from the in-process counter), persisted, then the counter is manually
    reset to imitate a fresh process, the store is reloaded from disk, and
    a brand-new constraint is added -- its id must not collide with
    anything already persisted.
    """
    persistence = _fresh_persistence_module()
    from constrainai.constraints import _counter_state

    db_path = str(tmp_path / "test6.db")

    store = ConstraintStore()
    for i in range(5):
        store.add(bound(var(f"x{i}"), Operator.GE, const(i), i, f"x{i} >= {i}"))

    session = persistence.get_session(db_path)
    persistence.save_store(session, "conv-6", store)
    session.close()

    # Simulate a fresh process: reset the counter back to 1.
    _counter_state["next"] = 1

    session2 = persistence.get_session(db_path)
    loaded = persistence.load_store(session2, "conv-6")  # this must bump the counter back up
    new_constraint = bound(var("new_var"), Operator.GE, const(1), 6, "brand new after restart")
    loaded.add(new_constraint)  # must not raise ValueError (duplicate id)
    session2.close()

    existing_ids = {c.id for c in store.all()}
    assert new_constraint.id not in existing_ids
