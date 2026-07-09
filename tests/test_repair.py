import pytest

from constrainai.constraints import Constraint, ConstraintKind, Operator
from constrainai.expressions import var, const, add
from constrainai.repair import suggest_repairs, verify_repair, RepairCandidate
from constrainai.shrink import shrink_to_subset_minimal
from constrainai.solver import check_constraints, CheckResult


def bound(lhs, op, rhs, turn, text):
    return Constraint(
        kind=ConstraintKind.BOUND, lhs=lhs, operator=op, rhs=rhs,
        source_turn=turn, source_text=text,
    )


def budget_example():
    return [
        bound(var("budget"), Operator.LE, const(20000), 1, "Budget must stay under 20k"),
        bound(var("gpu_cost"), Operator.GE, const(14000), 2, "GPU costs at least 14k"),
        bound(var("ram_cost"), Operator.GE, const(8000), 3, "RAM costs at least 8k"),
        bound(var("storage_cost"), Operator.GE, const(2000), 4, "Reserve 2k for storage"),
        bound(
            add(var("gpu_cost"), var("ram_cost"), var("storage_cost")),
            Operator.LE, var("budget"), 5, "gpu + ram + storage <= budget",
        ),
    ]


def test_budget_repair_suggests_increase_by_exactly_4000():
    constraints = budget_example()
    assert check_constraints(constraints).result == CheckResult.UNSAT

    candidates = suggest_repairs(constraints)
    assert len(candidates) >= 1

    budget_repairs = [c for c in candidates if c.variable_name == "budget"]
    assert len(budget_repairs) == 1
    repair = budget_repairs[0]

    assert repair.direction == "increase"
    assert repair.original_value == 20000
    assert repair.new_value == pytest.approx(24000)
    assert repair.delta == pytest.approx(4000)
    assert repair.verified_sat is True


def test_every_candidate_is_independently_verified_sat():
    constraints = budget_example()
    candidates = suggest_repairs(constraints)
    assert len(candidates) >= 1
    for c in candidates:
        assert verify_repair(constraints, c) is True
        assert c.verified_sat is True


def test_gpu_and_ram_and_storage_each_have_a_decrease_repair():
    constraints = budget_example()
    candidates = suggest_repairs(constraints)
    by_var = {c.variable_name: c for c in candidates}

    assert "gpu_cost" in by_var
    assert by_var["gpu_cost"].direction == "decrease"
    assert by_var["gpu_cost"].new_value == pytest.approx(10000)

    assert "ram_cost" in by_var
    assert by_var["ram_cost"].direction == "decrease"
    assert by_var["ram_cost"].new_value == pytest.approx(4000)

    assert "storage_cost" in by_var
    assert by_var["storage_cost"].direction == "decrease"
    assert by_var["storage_cost"].new_value == pytest.approx(-2000)


def test_relation_constraint_is_not_a_repair_candidate():
    # The sum<=budget constraint has no single Const threshold to adjust,
    # so it must never appear as a repair target.
    constraints = budget_example()
    candidates = suggest_repairs(constraints)
    relation_ids = {c.id for c in constraints if c.kind == ConstraintKind.RELATION}
    assert all(c.constraint.id not in relation_ids for c in candidates)


def test_repairs_computed_on_shrunk_core_but_verified_against_full_set():
    constraints = budget_example()
    shrunk = shrink_to_subset_minimal(constraints)
    # In this example the core equals the full set, but exercise the
    # two-argument form anyway to prove it plumbs through correctly.
    candidates = suggest_repairs(shrunk.minimal_core, full_active_set=constraints)
    assert len(candidates) >= 1
    for c in candidates:
        assert verify_repair(constraints, c) is True


def test_satisfiable_set_yields_no_repairs_needed():
    constraints = [
        bound(var("budget"), Operator.LE, const(50000), 1, "budget <= 50000"),
        bound(var("gpu_cost"), Operator.GE, const(14000), 2, "gpu >= 14000"),
    ]
    assert check_constraints(constraints).result == CheckResult.SAT
    # Nothing is actually binding toward infeasibility, so no genuine
    # repair candidates should be produced (both bounds are already
    # satisfied comfortably and are not the cause of any conflict).
    candidates = suggest_repairs(constraints)
    assert candidates == []


def test_repair_candidate_describe_mentions_provenance():
    constraints = budget_example()
    candidates = suggest_repairs(constraints)
    budget_repair = next(c for c in candidates if c.variable_name == "budget")
    desc = budget_repair.describe()
    assert "budget" in desc
    assert "Budget must stay under 20k" in desc
    assert "Verified" in desc


def test_candidates_sorted_by_smallest_delta_first_within_same_hardness():
    constraints = budget_example()
    candidates = suggest_repairs(constraints)
    deltas = [abs(c.delta) for c in candidates]
    assert deltas == sorted(deltas)
