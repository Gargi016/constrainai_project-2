import z3
import pytest

from constrainai.compiler import Z3Compiler
from constrainai.constraints import Constraint, ConstraintKind, Operator
from constrainai.expressions import var, const, add, sub


def test_compile_var_reuses_same_z3_symbol():
    compiler = Z3Compiler()
    a = compiler.compile_expression(var("budget"))
    b = compiler.compile_expression(var("budget"))
    # Same Python object identity for the underlying Z3 term.
    assert a.eq(b)
    assert len(compiler.variables()) == 1


def test_compile_const():
    compiler = Z3Compiler()
    term = compiler.compile_expression(const(20000))
    s = z3.Solver()
    s.add(term == 20000)
    assert s.check() == z3.sat


def test_compile_sum_of_three_vars():
    compiler = Z3Compiler()
    expr = add(var("gpu_cost"), var("ram_cost"), var("storage_cost"))
    term = compiler.compile_expression(expr)
    assert len(compiler.variables()) == 3


def test_compile_diff():
    compiler = Z3Compiler()
    expr = sub(var("project_b_start"), var("project_a_end"))
    term = compiler.compile_expression(expr)
    s = z3.Solver()
    pb, pa = compiler.z3_var("project_b_start"), compiler.z3_var("project_a_end")
    s.add(pb == 10, pa == 4)
    s.add(term == 6)
    assert s.check() == z3.sat


def test_compile_constraint_le():
    compiler = Z3Compiler()
    c = Constraint(
        kind=ConstraintKind.BOUND, lhs=var("budget"), operator=Operator.LE, rhs=const(20000),
        source_turn=1, source_text="budget <= 20000",
    )
    formula = compiler.compile_constraint(c)
    s = z3.Solver()
    s.add(formula)
    s.add(compiler.z3_var("budget") == 25000)
    assert s.check() == z3.unsat  # 25000 <= 20000 is false


def test_compile_constraint_unsupported_operator_raises():
    compiler = Z3Compiler()
    c = Constraint(
        kind=ConstraintKind.DEPENDENCY, lhs=var("gpu"), operator=Operator.REQUIRES, rhs=var("psu"),
        source_turn=1, source_text="gpu requires psu",
    )
    with pytest.raises(NotImplementedError):
        compiler.compile_constraint(c)
