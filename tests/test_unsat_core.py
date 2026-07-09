from constrainai.constraints import Constraint, ConstraintKind, Operator
from constrainai.expressions import var, const, add
from constrainai.unsat_core import extract_unsat_core


def bound(lhs, op, rhs, turn, text):
    return Constraint(
        kind=ConstraintKind.BOUND, lhs=lhs, operator=op, rhs=rhs,
        source_turn=turn, source_text=text,
    )


def test_sat_set_returns_none():
    constraints = [bound(var("budget"), Operator.LE, const(20000), 1, "budget <= 20000")]
    assert extract_unsat_core(constraints) is None


def test_unsat_core_maps_back_to_constraints_with_provenance():
    constraints = [
        bound(var("budget"), Operator.LE, const(20000), 1, "Budget must stay under 20k"),
        bound(var("gpu_cost"), Operator.GE, const(14000), 2, "GPU costs at least 14k"),
        bound(var("ram_cost"), Operator.GE, const(8000), 3, "RAM costs at least 8k"),
        bound(var("storage_cost"), Operator.GE, const(2000), 4, "Reserve 2k for storage"),
        bound(
            add(var("gpu_cost"), var("ram_cost"), var("storage_cost")),
            Operator.LE, var("budget"), 5, "gpu + ram + storage <= budget",
        ),
    ]
    result = extract_unsat_core(constraints)
    assert result is not None
    assert result.is_unsat
    assert len(result.raw_core) >= 1
    for c in result.raw_core:
        assert isinstance(c, Constraint)
        assert c.source_text  # provenance survived the round trip
    desc = result.describe()
    assert "UNSAT" in desc
