"""
Solver layer for ConstrainAI.

Wraps a z3.Solver and adds *tracked* assertions: every active Constraint is
asserted via `assert_and_track(formula, label)` where `label` is a fresh
boolean tracking constant uniquely associated with that constraint's id.
This is what lets us later ask Z3 for an `unsat_core()` and map the
returned tracking labels straight back to Constraint objects (and from
there to source turns / source text).

Only hard constraints participate in the base feasibility check; soft
constraints are exposed separately so the (future) repair engine can
choose to relax them under a priority ordering. That distinction is kept
out of this module's core check() path to keep the MVP's SAT/UNSAT
semantics unambiguous: "is the hard constraint set satisfiable".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import z3

from constrainai.compiler import Z3Compiler
from constrainai.constraints import Constraint, Hardness


class CheckResult(str, Enum):
    SAT = "sat"
    UNSAT = "unsat"
    UNKNOWN = "unknown"  # z3 returned unknown (should not happen for pure LRA, kept for honesty)


@dataclass
class SolveReport:
    result: CheckResult
    # Populated only when result == UNSAT: the raw list of tracking labels
    # z3 says are jointly responsible, in *no particular minimality
    # guarantee* (see unsat_core.py / shrink.py for that).
    raw_unsat_core_labels: Optional[List[str]] = None
    model: Optional[Dict[str, float]] = None  # populated only when result == SAT


class TrackedSolver:
    """
    Builds a z3.Solver from a list of Constraint objects, tracking each
    constraint by its own id so unsat cores can be mapped back to
    Constraint objects directly (no separate label->id table needed).
    """

    def __init__(self, constraints: List[Constraint]):
        # Only hard constraints are asserted for the base SAT/UNSAT check;
        # soft constraints are recorded but not asserted here.
        self.compiler = Z3Compiler()
        self.hard_constraints: List[Constraint] = [
            c for c in constraints if c.hardness == Hardness.HARD
        ]
        self.soft_constraints: List[Constraint] = [
            c for c in constraints if c.hardness == Hardness.SOFT
        ]
        self._by_id: Dict[str, Constraint] = {c.id: c for c in self.hard_constraints}

        self.solver = z3.Solver()
        # z3's unsat_core() only reports on assert_and_track'd formulas, and
        # tracking constants must be distinct z3.Bool objects. We use the
        # constraint id string directly as the tracking constant name so
        # label -> Constraint is a simple dict lookup.
        for c in self.hard_constraints:
            formula = self.compiler.compile_constraint(c)
            tracker = z3.Bool(c.id)
            self.solver.assert_and_track(formula, tracker)

    def constraint_for_label(self, label: str) -> Constraint:
        return self._by_id[label]

    def check(self) -> SolveReport:
        result = self.solver.check()
        if result == z3.sat:
            model = self.solver.model()
            values: Dict[str, float] = {}
            for name, z3var in self.compiler.variables().items():
                m_val = model.eval(z3var, model_completion=True)
                values[name] = z3_numeral_to_float(m_val)
            return SolveReport(result=CheckResult.SAT, model=values)
        if result == z3.unsat:
            core = self.solver.unsat_core()
            labels = [str(lbl) for lbl in core]
            return SolveReport(result=CheckResult.UNSAT, raw_unsat_core_labels=labels)
        return SolveReport(result=CheckResult.UNKNOWN)


def z3_numeral_to_float(value: z3.ExprRef) -> float:
    """Convert a Z3 numeral (Real/Int result) into a Python float."""
    if z3.is_algebraic_value(value):
        value = value.approx(20)
    if isinstance(value, z3.RatNumRef):
        return float(value.numerator_as_long()) / float(value.denominator_as_long())
    if isinstance(value, z3.IntNumRef):
        return float(value.as_long())
    # Fallback: parse from string representation, e.g. "5", "5/2"
    s = str(value)
    if "/" in s:
        num, den = s.split("/")
        return float(num) / float(den)
    return float(s)


def check_constraints(constraints: List[Constraint]) -> SolveReport:
    """Convenience function: build a TrackedSolver and check it in one call."""
    return TrackedSolver(constraints).check()
