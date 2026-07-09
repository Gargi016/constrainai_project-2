import pytest

from constrainai.constraints import Constraint, ConstraintKind, Operator
from constrainai.expressions import var, const, add
from constrainai.shrink import shrink_to_subset_minimal, verify_subset_minimal, is_unsat


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


def test_shrink_raises_on_non_unsat_input():
    with pytest.raises(ValueError):
        shrink_to_subset_minimal([bound(var("budget"), Operator.LE, const(20000), 1, "budget <= 20000")])


def test_shrink_raises_on_empty_input():
    with pytest.raises(ValueError):
        shrink_to_subset_minimal([])


def test_budget_example_minimal_core_is_all_five():
    # In this example every one of the five constraints is load-bearing:
    # removing any single one makes the remainder satisfiable (e.g. dropping
    # the sum<=budget relation, or dropping any individual lower/upper bound
    # lets the free variable absorb the slack). So the subset-minimal core
    # equals the full set here -- that's a real, checkable property, not an
    # assumption.
    constraints = budget_example()
    result = shrink_to_subset_minimal(constraints)
    assert {c.id for c in result.minimal_core} == {c.id for c in constraints}
    assert verify_subset_minimal(constraints, result.minimal_core)


def test_shrink_removes_a_truly_redundant_constraint():
    constraints = budget_example()
    # Add a redundant, strictly weaker restatement of the gpu lower bound.
    # It contributes no new information (14000 already implies >= 10000),
    # so it must NOT survive shrinking.
    redundant = bound(var("gpu_cost"), Operator.GE, const(10000), 6, "gpu costs at least 10k (redundant)")
    all_constraints = constraints + [redundant]

    assert is_unsat(all_constraints)
    result = shrink_to_subset_minimal(all_constraints)

    minimal_ids = {c.id for c in result.minimal_core}
    assert redundant.id not in minimal_ids
    assert minimal_ids == {c.id for c in constraints}
    assert verify_subset_minimal(all_constraints, result.minimal_core)


def test_shrink_removes_a_completely_unrelated_constraint():
    constraints = budget_example()
    unrelated = bound(var("project_b_start"), Operator.GE, const(0), 7, "unrelated scheduling fact")
    all_constraints = constraints + [unrelated]

    result = shrink_to_subset_minimal(all_constraints)
    minimal_ids = {c.id for c in result.minimal_core}
    assert unrelated.id not in minimal_ids
    assert verify_subset_minimal(all_constraints, result.minimal_core)


def test_verify_subset_minimal_rejects_a_non_minimal_set():
    constraints = budget_example()
    redundant = bound(var("gpu_cost"), Operator.GE, const(10000), 6, "gpu costs at least 10k (redundant)")
    all_constraints = constraints + [redundant]
    # The full 6-constraint set is UNSAT but NOT subset-minimal, since the
    # redundant constraint can be dropped without losing UNSAT.
    assert is_unsat(all_constraints)
    assert verify_subset_minimal(all_constraints, all_constraints) is False


def test_solver_calls_are_bounded_linearly_in_input_size():
    constraints = budget_example()
    result = shrink_to_subset_minimal(constraints)
    # Deletion-based shrinking: at most 1 initial check + 1 check per
    # constraint in the input.
    assert result.solver_calls <= len(constraints) + 1
