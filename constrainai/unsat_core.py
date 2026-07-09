"""
Unsat core extraction for ConstrainAI.

IMPORTANT TECHNICAL CAVEAT (do not remove or soften this):
z3's `Solver.unsat_core()` returns *a* set of tracked assertions sufficient
to prove unsatisfiability, but it is NOT guaranteed to be subset-minimal.
Z3 may return a superset of the true minimal conflict. This module only
extracts and maps that raw core; it makes no minimality claim. Use
`shrink.py`'s deletion-based shrinking to obtain a set that is provably
subset-minimal.

This module's job is narrow and mechanical:
    1. Run the tracked solver.
    2. If UNSAT, take the raw core labels z3 reports.
    3. Map each label back to its originating Constraint object.
    4. Package the result with enough provenance (source_turn, source_text)
       to explain the conflict to a user.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from constrainai.constraints import Constraint
from constrainai.solver import CheckResult, TrackedSolver


@dataclass
class UnsatCoreResult:
    is_unsat: bool
    # The raw core straight from z3 -- NOT guaranteed minimal.
    raw_core: List[Constraint]

    def describe(self) -> str:
        if not self.is_unsat:
            return "Constraint set is satisfiable; no conflict to report."
        lines = ["UNSAT. Z3's raw (not-necessarily-minimal) conflicting set:"]
        lines.extend(f"  - {c.describe()}" for c in self.raw_core)
        return "\n".join(lines)


def extract_unsat_core(constraints: List[Constraint]) -> Optional[UnsatCoreResult]:
    """
    Check `constraints` for satisfiability. If SAT, return None (there is no
    core to extract). If UNSAT, return the raw core mapped back to
    Constraint objects, explicitly unqualified as minimal.
    """
    solver = TrackedSolver(constraints)
    report = solver.check()

    if report.result != CheckResult.UNSAT:
        return None

    raw_core = [solver.constraint_for_label(lbl) for lbl in report.raw_unsat_core_labels or []]
    return UnsatCoreResult(is_unsat=True, raw_core=raw_core)
