import pytest

from constrainai.store import ConstraintStore, ConstraintNotFound
from constrainai.constraints import Constraint, ConstraintKind, Operator, ConstraintStatus
from constrainai.expressions import var, const


def make_budget_constraint(value=20000, turn=1, text="Budget must stay under 20k"):
    return Constraint(
        kind=ConstraintKind.BOUND, lhs=var("budget"), operator=Operator.LE, rhs=const(value),
        source_turn=turn, source_text=text,
    )


def test_add_and_get():
    store = ConstraintStore()
    c = make_budget_constraint()
    store.add(c)
    assert store.get(c.id) is c


def test_get_missing_raises():
    store = ConstraintStore()
    with pytest.raises(ConstraintNotFound):
        store.get("does-not-exist")


def test_active_excludes_retracted_and_superseded():
    store = ConstraintStore()
    c1 = make_budget_constraint()
    store.add(c1)
    assert store.active() == [c1]

    store.retract(c1.id)
    assert store.active() == []
    assert store.by_status(ConstraintStatus.RETRACTED) == [c1]


def test_revise_supersedes_old_and_adds_new():
    store = ConstraintStore()
    old = make_budget_constraint(value=20000, turn=1, text="Budget must stay under 20k")
    store.add(old)

    new = make_budget_constraint(value=27000, turn=5, text="Actually increase budget to 27k")
    store.revise(old.id, new)

    assert old.status == ConstraintStatus.SUPERSEDED
    assert new.status == ConstraintStatus.ACTIVE
    assert new.supersedes == old.id
    assert store.active() == [new]
    # History is preserved.
    assert old in store.all()


def test_find_active_on_variable():
    store = ConstraintStore()
    budget_c = make_budget_constraint()
    ram_c = Constraint(
        kind=ConstraintKind.BOUND, lhs=var("ram_cost"), operator=Operator.GE, rhs=const(8000),
        source_turn=2, source_text="RAM costs at least 8k",
    )
    store.add(budget_c)
    store.add(ram_c)

    assert store.find_active_on_variable("budget") == [budget_c]
    assert store.find_active_on_variable("ram_cost") == [ram_c]
    assert store.find_active_on_variable("nonexistent") == []


def test_add_duplicate_id_rejected():
    store = ConstraintStore()
    c = make_budget_constraint()
    store.add(c)
    with pytest.raises(ValueError):
        store.add(c)
