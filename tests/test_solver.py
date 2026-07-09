from constrainai.constraints import Constraint, ConstraintKind, Operator, Hardness
from constrainai.expressions import var, const, add
from constrainai.solver import TrackedSolver, CheckResult, check_constraints


def bound(lhs, op, rhs, turn, text, hardness=Hardness.HARD):
    return Constraint(
        kind=ConstraintKind.BOUND, lhs=lhs, operator=op, rhs=rhs,
        source_turn=turn, source_text=text, hardness=hardness,
    )


def test_empty_constraint_set_is_sat():
    report = check_constraints([])
    assert report.result == CheckResult.SAT


def test_simple_satisfiable_set():
    constraints = [
        bound(var("budget"), Operator.LE, const(20000), 1, "budget <= 20000"),
        bound(var("gpu_cost"), Operator.GE, const(14000), 2, "gpu >= 14000"),
    ]
    report = check_constraints(constraints)
    assert report.result == CheckResult.SAT
    assert report.model["budget"] <= 20000
    assert report.model["gpu_cost"] >= 14000


def test_budget_example_is_unsat():
    constraints = [
        bound(var("budget"), Operator.LE, const(20000), 1, "Budget must stay under 20k"),
        bound(var("gpu_cost"), Operator.GE, const(14000), 2, "GPU costs at least 14k"),
        bound(var("ram_cost"), Operator.GE, const(8000), 3, "RAM costs at least 8k"),
        bound(var("storage_cost"), Operator.GE, const(2000), 4, "Reserve 2k for storage"),
        bound(
            add(var("gpu_cost"), var("ram_cost"), var("storage_cost")),
            Operator.LE, var("budget"), 5,
            "gpu + ram + storage <= budget",
        ),
    ]
    report = check_constraints(constraints)
    assert report.result == CheckResult.UNSAT
    assert report.raw_unsat_core_labels  # non-empty
    # every reported label should map back to one of our constraint ids
    ids = {c.id for c in constraints}
    assert set(report.raw_unsat_core_labels).issubset(ids)


def test_soft_constraints_do_not_affect_base_sat_check():
    hard = bound(var("budget"), Operator.LE, const(20000), 1, "budget <= 20000")
    # A soft constraint that directly contradicts the hard one should NOT
    # flip the base check to UNSAT, since only hard constraints are asserted.
    soft_conflict = bound(
        var("budget"), Operator.GE, const(999999), 2, "nice to have a huge budget",
        hardness=Hardness.SOFT,
    )
    solver = TrackedSolver([hard, soft_conflict])
    assert solver.hard_constraints == [hard]
    assert solver.soft_constraints == [soft_conflict]
    report = solver.check()
    assert report.result == CheckResult.SAT


def test_tracked_solver_maps_label_back_to_constraint():
    c = bound(var("budget"), Operator.LE, const(20000), 1, "budget <= 20000")
    solver = TrackedSolver([c])
    assert solver.constraint_for_label(c.id) is c
