"""
Z3 compiler for ConstrainAI.

Responsibility: turn typed Expression / Constraint IR objects into Z3
ArithRef / BoolRef terms. This is the ONLY module that imports z3 for the
purpose of building formulas (solver.py imports z3 too, but only to drive
the solving procedure, not to interpret the IR).

Design notes:
- One Z3 Real() variable per distinct variable name. We use Real (not Int)
  because planning quantities like money are naturally continuous and this
  avoids spurious UNSATs from integer rounding; nothing in the IR requires
  integrality. If integral semantics are needed later, this is the single
  place to change it.
- REQUIRES / EXCLUDES / IN are modeled as boolean-level relations for
  completeness of the IR, but the MVP solver focuses on BOUND / EQUALITY /
  RELATION kinds (linear arithmetic), which is what the budget example and
  the First Task require. Unsupported operator/kind combinations raise a
  clear NotImplementedError rather than silently producing wrong formulas.
"""

from __future__ import annotations

from typing import Dict, Optional

import z3

from constrainai.constraints import Constraint, Operator
from constrainai.expressions import Const, Diff, Expression, Neg, Scale, Sum, Var

# Keyed by id(expression_node) -> z3 term to substitute in its place. Used by
# the repair engine to ask "what if this specific Const node were a free
# variable instead?" without needing a separate expression-tree rewriter.
NodeOverride = Dict[int, z3.ArithRef]


class Z3Compiler:
    """
    Compiles Expression/Constraint IR to Z3 terms, maintaining a shared
    symbol table so the same variable name always maps to the same Z3 Real
    across every constraint compiled by this instance.
    """

    def __init__(self) -> None:
        self._vars: Dict[str, z3.ArithRef] = {}

    def z3_var(self, name: str) -> z3.ArithRef:
        """Get (creating if necessary) the Z3 Real constant for a variable name."""
        if name not in self._vars:
            self._vars[name] = z3.Real(name)
        return self._vars[name]

    def variables(self) -> Dict[str, z3.ArithRef]:
        """Return the symbol table built up so far (name -> Z3 Real)."""
        return dict(self._vars)

    def compile_expression(
        self, expr: Expression, override: Optional[NodeOverride] = None
    ) -> z3.ArithRef:
        """
        Recursively compile an Expression node into a Z3 arithmetic term.

        If `override` is given and `id(expr)` is a key in it, the associated
        Z3 term is returned directly instead of compiling `expr` normally.
        This lets the repair engine substitute one specific Const node (by
        object identity, not by value) with a free Z3 variable, so it can
        ask Z3 "what is the tightest value this constant could take?" while
        every other occurrence of the same numeric value elsewhere in the
        constraint set is left untouched.
        """
        if override and id(expr) in override:
            return override[id(expr)]
        if isinstance(expr, Var):
            return self.z3_var(expr.name)
        if isinstance(expr, Const):
            return z3.RealVal(expr.value)
        if isinstance(expr, Neg):
            return -self.compile_expression(expr.operand, override)
        if isinstance(expr, Scale):
            return z3.RealVal(expr.factor) * self.compile_expression(expr.operand, override)
        if isinstance(expr, Sum):
            if not expr.terms:
                return z3.RealVal(0)
            terms = [self.compile_expression(t, override) for t in expr.terms]
            total = terms[0]
            for t in terms[1:]:
                total = total + t
            return total
        if isinstance(expr, Diff):
            return self.compile_expression(expr.left, override) - self.compile_expression(
                expr.right, override
            )
        raise NotImplementedError(f"Unsupported expression node: {expr!r}")

    def compile_constraint(
        self, constraint: Constraint, override: Optional[NodeOverride] = None
    ) -> z3.BoolRef:
        """Compile a Constraint into a single Z3 boolean formula."""
        lhs = self.compile_expression(constraint.lhs, override)
        rhs = self.compile_expression(constraint.rhs, override)
        op = constraint.operator

        if op == Operator.LE:
            return lhs <= rhs
        if op == Operator.GE:
            return lhs >= rhs
        if op == Operator.EQ:
            return lhs == rhs
        if op == Operator.NE:
            return lhs != rhs
        # REQUIRES / EXCLUDES / IN are reserved for boolean/categorical
        # variables and are out of scope for the linear-arithmetic MVP core.
        raise NotImplementedError(
            f"Operator {op.value!r} is not yet supported by the linear-arithmetic "
            f"MVP compiler (constraint {constraint.id})."
        )
