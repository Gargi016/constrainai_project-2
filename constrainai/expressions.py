"""
Typed Expression IR for ConstrainAI.

Expressions form a small algebra sufficient for linear arithmetic over
numeric planning variables (costs, budgets, dates-as-integers, etc).

Supported node types:
    Var       - a named numeric variable (e.g. "gpu_cost")
    Const     - a numeric literal
    Sum       - n-ary addition of sub-expressions
    Diff      - binary subtraction (left - right)
    Neg       - unary negation
    Scale     - multiplication of an expression by a numeric constant (linear only)

This is intentionally NOT a general-purpose arithmetic AST: no free-form
multiplication of two variables, no division. That keeps every expression
compilable to a Z3 *linear* arithmetic term, which keeps solving fast and
keeps unsat-core / repair reasoning tractable.

Each node exposes:
    - variables() -> set[str]   : all variable names referenced, recursively
    - __str__                    : human-readable rendering, used in explanations
"""

from __future__ import annotations

from typing import List, Literal, Union
from pydantic import BaseModel, Field


class Var(BaseModel):
    """A reference to a named numeric variable, e.g. `budget` or `gpu_cost`."""

    node: Literal["var"] = "var"
    name: str

    def variables(self) -> set[str]:
        return {self.name}

    def __str__(self) -> str:
        return self.name


class Const(BaseModel):
    """A numeric literal, e.g. `20000`."""

    node: Literal["const"] = "const"
    value: float

    def variables(self) -> set[str]:
        return set()

    def __str__(self) -> str:
        # Render integers without a trailing ".0" for readability.
        if float(self.value).is_integer():
            return str(int(self.value))
        return str(self.value)


class Neg(BaseModel):
    """Unary negation: -expr."""

    node: Literal["neg"] = "neg"
    operand: "Expression"

    def variables(self) -> set[str]:
        return self.operand.variables()

    def __str__(self) -> str:
        return f"-({self.operand})"


class Scale(BaseModel):
    """Multiplication of an expression by a fixed numeric constant: k * expr."""

    node: Literal["scale"] = "scale"
    factor: float
    operand: "Expression"

    def variables(self) -> set[str]:
        return self.operand.variables()

    def __str__(self) -> str:
        return f"{self.factor}*({self.operand})"


class Sum(BaseModel):
    """N-ary addition: term_0 + term_1 + ... + term_{n-1}."""

    node: Literal["sum"] = "sum"
    terms: List["Expression"] = Field(default_factory=list)

    def variables(self) -> set[str]:
        result: set[str] = set()
        for t in self.terms:
            result |= t.variables()
        return result

    def __str__(self) -> str:
        return " + ".join(str(t) for t in self.terms)


class Diff(BaseModel):
    """Binary subtraction: left - right."""

    node: Literal["diff"] = "diff"
    left: "Expression"
    right: "Expression"

    def variables(self) -> set[str]:
        return self.left.variables() | self.right.variables()

    def __str__(self) -> str:
        return f"({self.left} - {self.right})"


Expression = Union[Var, Const, Neg, Scale, Sum, Diff]

# Resolve forward references now that all node types exist.
Neg.model_rebuild()
Scale.model_rebuild()
Sum.model_rebuild()
Diff.model_rebuild()


# --------------------------------------------------------------------------
# Convenience constructors, so extraction code / tests can write:
#     var("gpu_cost") + var("ram_cost") <= var("budget")
# via plain function calls rather than hand-building Pydantic nodes.
# --------------------------------------------------------------------------

def var(name: str) -> Var:
    return Var(name=name)


def const(value: float) -> Const:
    return Const(value=value)


def add(*exprs: "Expression") -> Sum:
    return Sum(terms=list(exprs))


def sub(left: "Expression", right: "Expression") -> Diff:
    return Diff(left=left, right=right)


def neg(expr: "Expression") -> Neg:
    return Neg(operand=expr)


def scale(factor: float, expr: "Expression") -> Scale:
    return Scale(factor=factor, operand=expr)


def all_variables(expr: "Expression") -> set[str]:
    """Return the set of variable names referenced by an expression."""
    return expr.variables()
