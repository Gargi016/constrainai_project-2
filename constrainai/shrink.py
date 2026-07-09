"""
Deletion-based subset-minimal core shrinking for ConstrainAI.

Given an UNSAT set of constraints C (typically z3's raw, not-necessarily-
minimal unsat core, but this algorithm works on any UNSAT set), this module
computes a set M subset-of C such that:

    (1) M is UNSAT
    (2) for every c in M: M \\ {c} is SAT      ("subset-minimal")

This is the classic deletion-based / QuickXplain-style linear shrinking
algorithm:

    M = C
    for c in list(C):
        if c not in M: continue
        candidate = M - {c}
        if candidate is UNSAT:
            M = candidate
        # else: c is load-bearing for unsatisfiability, keep it in M

Complexity: O(n) SAT calls in the worst case where n = |C| (each remaining
constraint is tried for removal once). This is the standard, well
understood cost of deletion-based minimization and is what the project
spec calls for at MVP stage -- it does NOT claim to find the smallest
possible conflict among *all* UNSAT subsets (that would require exploring
combinations, e.g. via QuickXplain's divide-and-conquer, or an MUS
enumerator). Subset-minimal != smallest. We only ever claim subset-minimal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from constrainai.constraints import Constraint
from constrainai.solver import CheckResult, check_constraints


@dataclass
class ShrinkResult:
    minimal_core: List[Constraint]
    solver_calls: int  # number of SAT/UNSAT checks performed, for cost measurement


def is_unsat(constraints: List[Constraint]) -> bool:
    return check_constraints(constraints).result == CheckResult.UNSAT


def shrink_to_subset_minimal(constraints: List[Constraint]) -> ShrinkResult:
    """
    Deletion-based shrinking. `constraints` must already be UNSAT; this is
    checked and enforced (raises ValueError otherwise) so callers can't
    silently get a bogus "minimal" result from a satisfiable input.
    """
    solver_calls = 0

    if not constraints:
        raise ValueError("Cannot shrink an empty constraint set")

    solver_calls += 1
    if not is_unsat(constraints):
        raise ValueError("Input constraint set is not UNSAT; nothing to shrink")

    minimal: List[Constraint] = list(constraints)

    # Iterate over a fixed snapshot of the starting ids; for each, try
    # removing it from the *current* working set (not the original), since
    # earlier removals in this loop affect what's still needed.
    for c in list(constraints):
        if c not in minimal:
            continue  # already removed by an earlier iteration
        candidate = [x for x in minimal if x.id != c.id]
        if not candidate:
            # Never remove the last remaining constraint -- an empty set is
            # trivially SAT, so this constraint is definitely load-bearing.
            continue
        solver_calls += 1
        if is_unsat(candidate):
            minimal = candidate
        # else: candidate became SAT, meaning c was necessary for
        # unsatisfiability -- keep it in `minimal`.

    return ShrinkResult(minimal_core=minimal, solver_calls=solver_calls)


def verify_subset_minimal(all_constraints_considered: List[Constraint], core: List[Constraint]) -> bool:
    """
    Independently verify the two defining properties of subset-minimality
    for `core`:
        (1) core is UNSAT
        (2) for every c in core, core \\ {c} is SAT

    This is a pure verification pass (re-runs the solver from scratch) used
    by tests and by the explanation layer to back up the "minimal" claim
    with an actual check rather than trusting the shrinking algorithm blindly.
    """
    if not is_unsat(core):
        return False
    for c in core:
        reduced = [x for x in core if x.id != c.id]
        if reduced and is_unsat(reduced):
            return False
        if not reduced:
            # Removing the last constraint from a 1-element UNSAT core must
            # yield SAT (empty constraint sets are vacuously satisfiable).
            if is_unsat(reduced):
                return False
    return True
