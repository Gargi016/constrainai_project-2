"""
Repair engine for ConstrainAI.

Given an UNSAT active constraint set (typically the subset-minimal conflict
core from shrink.py, but this works on any UNSAT set), this module proposes
CONCRETE, SOLVER-VERIFIED repairs -- not vague advice like "reduce some
costs." Every number this module reports is computed by Z3, then
independently re-checked by re-solving the full constraint set with the
candidate value plugged in.

Scope of this MVP: repairs that adjust the numeric threshold of a single
BOUND-kind constraint (`var <= k` or `var >= k`, in either lhs/rhs order).
This directly covers the example in the spec:

    budget <= 20000
    gpu_cost >= 14000
    ram_cost >= 8000
    storage_cost >= 2000
    gpu_cost + ram_cost + storage_cost <= budget

    -> "Increase budget by at least 4000"   (relax the upper bound)
    -> "Decrease gpu_cost's floor by at least 4000" (relax a lower bound)
    -> ... etc, one candidate per adjustable bound in the conflict.

How the tightest value is computed
-----------------------------------
For a target constraint `var OP k` (k a Const node), we:
  1. Build a fresh Z3 Optimize() context.
  2. Assert every OTHER hard, active constraint normally.
  3. Assert the target constraint with its Const node replaced by a fresh
     Z3 real variable `k'` (via Z3Compiler's node-override mechanism), so
     `k'` is now a free unknown rather than a fixed number.
  4. Ask Z3 to MINIMIZE k' (if OP is <=, since relaxing an upper bound means
     raising it, and we want the smallest sufficient raise) or MAXIMIZE k'
     (if OP is >=, since relaxing a lower bound means lowering it, and we
     want the largest sufficient floor still small enough to work).
  5. Read k' out of the optimizer's model. That is the tightest value for
     which the rest of the system is simultaneously satisfiable.

This is a real linear-programming computation, not a heuristic search. It
only fails to find a bound when the remaining hard constraints (excluding
the target) are themselves already UNSAT, or are unbounded in the relevant
direction (Z3 reports the objective as unbounded) -- both are detected and
reported rather than silently guessed.

Every candidate's final value is then plugged back into a COMPLETE fresh
solve of the full constraint set (`verify_repair`) before being labeled
verified. A candidate is only surfaced to the user if that final check
passes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import z3

from constrainai.compiler import Z3Compiler
from constrainai.constraints import Constraint, ConstraintKind, Hardness, Operator
from constrainai.expressions import Const, Var
from constrainai.solver import CheckResult, check_constraints, z3_numeral_to_float


@dataclass
class RepairCandidate:
    """A single concrete, solver-verified repair proposal."""

    constraint: Constraint
    variable_name: str
    original_value: float
    new_value: float
    verified_sat: bool

    @property
    def delta(self) -> float:
        return self.new_value - self.original_value

    @property
    def direction(self) -> str:
        return "increase" if self.delta > 0 else "decrease"

    def describe(self) -> str:
        verb = "Increase" if self.direction == "increase" else "Decrease"
        magnitude = abs(self.delta)
        return (
            f"{verb} the threshold on {self.variable_name} by at least "
            f"{magnitude:,.2f} (from {self.original_value:,.2f} to "
            f"{self.new_value:,.2f}) — relaxes [{self.constraint.id}] "
            f"{self.constraint} (from turn {self.constraint.source_turn}: "
            f"\"{self.constraint.source_text}\"). "
            f"{'Verified: restores SAT.' if self.verified_sat else 'WARNING: not solver-verified.'}"
        )


def _bound_target(constraint: Constraint) -> Optional[tuple[str, Const]]:
    """
    If `constraint` is a simple single-variable bound (`var OP const` or
    `const OP var`), return (variable_name, const_node). Otherwise (e.g. a
    multi-variable RELATION constraint like `gpu+ram+storage <= budget`,
    which has no single adjustable numeric threshold) return None -- such
    constraints are not candidates for this repair strategy.
    """
    if constraint.kind != ConstraintKind.BOUND:
        return None
    if isinstance(constraint.lhs, Var) and isinstance(constraint.rhs, Const):
        return constraint.lhs.name, constraint.rhs
    if isinstance(constraint.rhs, Var) and isinstance(constraint.lhs, Const):
        return constraint.rhs.name, constraint.lhs
    return None


def _compute_tightest_value(
    other_hard_constraints: List[Constraint], target: Constraint, const_node: Const
) -> Optional[float]:
    """
    Compute the tightest feasible value for `target`'s constant, holding all
    of `other_hard_constraints` fixed. Returns None if no finite tightest
    value exists (the remaining system is UNSAT even without the target, or
    the objective is unbounded).
    """
    compiler = Z3Compiler()
    opt = z3.Optimize()

    for c in other_hard_constraints:
        opt.add(compiler.compile_constraint(c))

    k = z3.Real(f"__repair_{target.id}")
    override = {id(const_node): k}
    formula = compiler.compile_constraint(target, override=override)
    opt.add(formula)

    if target.operator == Operator.LE:
        handle = opt.minimize(k)
    elif target.operator == Operator.GE:
        handle = opt.maximize(k)
    else:
        return None  # only <= / >= bounds are supported by this repair strategy

    result = opt.check()
    if result != z3.sat:
        return None

    # Z3 can report `sat` even when the objective itself is unbounded (e.g.
    # nothing else constrains this variable at all) -- in that case the
    # model is just some arbitrary feasible point, NOT the optimum, and
    # `handle.value()` renders as containing "oo" (infinity). Treat that as
    # "this bound isn't actually the thing causing infeasibility" rather
    # than reporting a meaningless number.
    obj_value = handle.value()
    if "oo" in str(obj_value):
        return None

    try:
        return z3_numeral_to_float(obj_value)
    except z3.Z3Exception:
        return None


def verify_repair(active_constraints: List[Constraint], candidate: RepairCandidate) -> bool:
    """
    Independently verify a candidate repair: build a fresh copy of the
    active constraint set with the candidate's constraint's constant
    replaced by its new value, and check the WHOLE set is SAT from scratch.
    This never trusts the optimizer's own internal state.
    """
    patched: List[Constraint] = []
    for c in active_constraints:
        if c.id == candidate.constraint.id:
            patched.append(_with_new_const_value(c, candidate.new_value))
        else:
            patched.append(c)
    report = check_constraints(patched)
    return report.result == CheckResult.SAT


def _with_new_const_value(constraint: Constraint, new_value: float) -> Constraint:
    """Return a copy of `constraint` with its Const-side threshold replaced."""
    data = constraint.model_dump()
    if isinstance(constraint.lhs, Const):
        data["lhs"] = {"node": "const", "value": new_value}
    elif isinstance(constraint.rhs, Const):
        data["rhs"] = {"node": "const", "value": new_value}
    else:
        raise ValueError(f"Constraint {constraint.id} has no Const side to patch")
    return Constraint.model_validate(data)


def suggest_repairs(
    conflict_core: List[Constraint], full_active_set: Optional[List[Constraint]] = None
) -> List[RepairCandidate]:
    """
    For every adjustable BOUND constraint in `conflict_core`, compute the
    tightest solver-verified relaxation that -- on its own -- would restore
    satisfiability of `full_active_set` (defaults to `conflict_core` itself
    if not given; pass the full active set when the core is a strict
    subset, so repairs are checked against everything the user has stated,
    not just the isolated conflict).

    Returned candidates are sorted with soft constraints first (cheaper to
    relax than a hard requirement), then by lower `priority` value first
    within the same hardness tier, then by smallest absolute delta -- i.e.
    the least disruptive change is suggested first. Only candidates that
    are independently verified to restore SAT are included.
    """
    full_set = full_active_set if full_active_set is not None else conflict_core
    hard_full = [c for c in full_set if c.hardness == Hardness.HARD]

    candidates: List[RepairCandidate] = []

    for target in conflict_core:
        target_info = _bound_target(target)
        if target_info is None:
            continue  # not a simple single-variable bound; skip
        var_name, const_node = target_info

        if target.hardness != Hardness.HARD:
            # Soft constraints can simply be dropped/relaxed by the caller;
            # this MVP's optimization-based repair only recomputes tight
            # numeric thresholds for HARD bounds, since soft constraints
            # aren't asserted in the base feasibility check to begin with.
            continue

        others = [c for c in hard_full if c.id != target.id]
        new_value = _compute_tightest_value(others, target, const_node)
        if new_value is None:
            continue  # remaining system infeasible regardless of this bound, or unbounded

        if new_value == const_node.value:
            continue  # this bound isn't actually binding; not a genuine repair

        candidate = RepairCandidate(
            constraint=target,
            variable_name=var_name,
            original_value=const_node.value,
            new_value=new_value,
            verified_sat=False,
        )
        candidate.verified_sat = verify_repair(full_set, candidate)
        if candidate.verified_sat:
            candidates.append(candidate)

    candidates.sort(
        key=lambda c: (
            0 if c.constraint.hardness == Hardness.SOFT else 1,
            c.constraint.priority,
            abs(c.delta),
        )
    )
    return candidates
