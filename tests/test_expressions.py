from constrainai.expressions import Var, Const, Sum, Diff, Neg, Scale, var, const, add, sub


def test_var_variables():
    v = var("budget")
    assert v.variables() == {"budget"}
    assert str(v) == "budget"


def test_const_str_integer_rendering():
    assert str(const(20000)) == "20000"
    assert str(const(2.5)) == "2.5"


def test_sum_collects_all_variables():
    expr = add(var("gpu_cost"), var("ram_cost"), var("storage_cost"))
    assert expr.variables() == {"gpu_cost", "ram_cost", "storage_cost"}


def test_diff_collects_both_sides_variables():
    expr = sub(var("project_b_start"), var("project_a_end"))
    assert expr.variables() == {"project_b_start", "project_a_end"}


def test_neg_and_scale_preserve_variables():
    expr = Scale(factor=2.0, operand=Neg(operand=var("x")))
    assert expr.variables() == {"x"}


def test_sum_of_zero_terms_has_no_variables():
    expr = Sum(terms=[])
    assert expr.variables() == set()


def test_nested_expression_str_rendering():
    expr = add(var("gpu_cost"), var("ram_cost"), var("storage_cost"))
    assert str(expr) == "gpu_cost + ram_cost + storage_cost"
