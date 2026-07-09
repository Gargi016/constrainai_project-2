"""
ConstrainAI: Conversational Constraint Solving with Minimal Conflict
Isolation and Repair.

This package currently implements the deterministic reasoning core:
expressions, constraint IR, constraint store, Z3 compilation, SAT/UNSAT
checking with tracked assertions, raw unsat core extraction, and
deletion-based subset-minimal core shrinking.

NL extraction, the repair engine, the FastAPI service, persistence, and the
frontend are later stages (see project README / implementation order) and
are not part of this module yet.
"""

from constrainai.expressions import Var, Const, Sum, Diff, Neg, Scale, var, const, add, sub
from constrainai.constraints import (
    Constraint,
    ConstraintKind,
    Operator,
    Hardness,
    ConstraintStatus,
)
from constrainai.store import ConstraintStore
from constrainai.compiler import Z3Compiler
from constrainai.solver import TrackedSolver, SolveReport, CheckResult, check_constraints
from constrainai.unsat_core import extract_unsat_core, UnsatCoreResult
from constrainai.shrink import shrink_to_subset_minimal, verify_subset_minimal, ShrinkResult
from constrainai.repair import suggest_repairs, verify_repair, RepairCandidate
from constrainai.extraction import Extractor, ExtractionOutcome, OutcomeKind

__all__ = [
    "Var", "Const", "Sum", "Diff", "Neg", "Scale", "var", "const", "add", "sub",
    "Constraint", "ConstraintKind", "Operator", "Hardness", "ConstraintStatus",
    "ConstraintStore",
    "Z3Compiler",
    "TrackedSolver", "SolveReport", "CheckResult", "check_constraints",
    "extract_unsat_core", "UnsatCoreResult",
    "shrink_to_subset_minimal", "verify_subset_minimal", "ShrinkResult",
    "suggest_repairs", "verify_repair", "RepairCandidate",
    "Extractor", "ExtractionOutcome", "OutcomeKind",
]
