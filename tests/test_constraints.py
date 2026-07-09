from constrainai.constraints import Constraint, ConstraintKind, Operator, Hardness, ConstraintStatus
from constrainai.expressions import var, const, add


def test_constraint_defaults():
    c = Constraint(
        kind=ConstraintKind.BOUND,
        lhs=var("budget"),
        operator=Operator.LE,
        rhs=const(20000),
        source_turn=1,
        source_text="Budget must stay under 20k",
    )
    assert c.status == ConstraintStatus.ACTIVE
    assert c.hardness == Hardness.HARD
    assert c.confidence == 1.0
    assert c.id.startswith("c")


def test_constraint_ids_are_unique():
    c1 = Constraint(
        kind=ConstraintKind.BOUND, lhs=var("x"), operator=Operator.LE, rhs=const(1),
        source_turn=1, source_text="x",
    )
    c2 = Constraint(
        kind=ConstraintKind.BOUND, lhs=var("y"), operator=Operator.LE, rhs=const(1),
        source_turn=2, source_text="y",
    )
    assert c1.id != c2.id


def test_constraint_variables_union_of_lhs_and_rhs():
    c = Constraint(
        kind=ConstraintKind.RELATION,
        lhs=add(var("gpu_cost"), var("ram_cost"), var("storage_cost")),
        operator=Operator.LE,
        rhs=var("budget"),
        source_turn=5,
        source_text="gpu + ram + storage <= budget",
    )
    assert c.variables() == {"gpu_cost", "ram_cost", "storage_cost", "budget"}


def test_constraint_str_and_describe():
    c = Constraint(
        kind=ConstraintKind.BOUND, lhs=var("gpu_cost"), operator=Operator.GE, rhs=const(14000),
        source_turn=2, source_text="GPU costs at least 14k",
    )
    assert str(c) == "gpu_cost >= 14000"
    desc = c.describe()
    assert c.id in desc
    assert "turn 2" in desc
    assert "GPU costs at least 14k" in desc


def test_constraint_status_transitions_are_settable():
    c = Constraint(
        kind=ConstraintKind.BOUND, lhs=var("ram_cost"), operator=Operator.GE, rhs=const(8000),
        source_turn=3, source_text="RAM costs at least 8k",
    )
    c.status = ConstraintStatus.RETRACTED
    assert c.status == ConstraintStatus.RETRACTED
    assert "retracted" in c.describe()
