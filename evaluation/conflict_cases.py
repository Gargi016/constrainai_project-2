"""
Conflict evaluation cases: directly-constructed constraint sets (bypassing
NL extraction, since these test the solving/repair pipeline in isolation)
across the same three domains, each with a known expected SAT/UNSAT
outcome and, for UNSAT cases, the expected exact subset-minimal conflict
set expressed as signatures (kind, lhs_str, operator, rhs_str) so
comparisons don't depend on auto-generated constraint ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from constrainai.constraints import Constraint, ConstraintKind, Operator
from constrainai.expressions import add, const, var
from constrainai.solver import CheckResult

Signature = Tuple[str, str, str, str]


def signature(c: Constraint) -> Signature:
    return (c.kind.value, str(c.lhs), c.operator.value, str(c.rhs))


def _bound(lhs, op, rhs, turn, text):
    return Constraint(
        kind=ConstraintKind.BOUND, lhs=lhs, operator=op, rhs=rhs,
        source_turn=turn, source_text=text,
    )


def _relation(lhs, op, rhs, turn, text):
    return Constraint(
        kind=ConstraintKind.RELATION, lhs=lhs, operator=op, rhs=rhs,
        source_turn=turn, source_text=text,
    )


@dataclass
class ConflictCase:
    name: str
    domain: str
    constraints: List[Constraint]
    expected_result: CheckResult
    expected_minimal_core_signatures: Optional[Set[Signature]] = None


CONFLICT_CASES: List[ConflictCase] = [
    # -- Budgeting ---------------------------------------------------------
    ConflictCase(
        name="budgeting_spec_conflict",
        domain="budgeting",
        constraints=[
            _bound(var("budget"), Operator.LE, const(20000), 1, "Budget must stay under 20k"),
            _bound(var("gpu_cost"), Operator.GE, const(14000), 2, "GPU costs at least 14k"),
            _bound(var("ram_cost"), Operator.GE, const(8000), 3, "RAM costs at least 8k"),
            _bound(var("storage_cost"), Operator.GE, const(2000), 4, "Reserve 2k for storage"),
            _relation(
                add(var("gpu_cost"), var("ram_cost"), var("storage_cost")),
                Operator.LE, var("budget"), 5, "gpu + ram + storage <= budget",
            ),
        ],
        expected_result=CheckResult.UNSAT,
        expected_minimal_core_signatures={
            ("bound", "budget", "<=", "20000"),
            ("bound", "gpu_cost", ">=", "14000"),
            ("bound", "ram_cost", ">=", "8000"),
            ("bound", "storage_cost", ">=", "2000"),
            ("relation", "gpu_cost + ram_cost + storage_cost", "<=", "budget"),
        },
    ),
    ConflictCase(
        name="budgeting_satisfiable",
        domain="budgeting",
        constraints=[
            _bound(var("budget"), Operator.LE, const(50000), 1, "Budget must stay under 50k"),
            _bound(var("gpu_cost"), Operator.GE, const(14000), 2, "GPU costs at least 14k"),
            _bound(var("ram_cost"), Operator.GE, const(8000), 3, "RAM costs at least 8k"),
            _bound(var("storage_cost"), Operator.GE, const(2000), 4, "Reserve 2k for storage"),
            _relation(
                add(var("gpu_cost"), var("ram_cost"), var("storage_cost")),
                Operator.LE, var("budget"), 5, "gpu + ram + storage <= budget",
            ),
        ],
        expected_result=CheckResult.SAT,
    ),

    # -- Hardware configuration -----------------------------------------
    ConflictCase(
        name="hardware_conflict",
        domain="hardware",
        constraints=[
            _bound(var("total_cost"), Operator.LE, const(15000), 1, "Total cost must stay under 15k"),
            _bound(var("cpu_cost"), Operator.GE, const(6000), 2, "CPU costs at least 6k"),
            _bound(var("gpu_cost"), Operator.GE, const(10000), 3, "GPU costs at least 10k"),
            _relation(
                add(var("cpu_cost"), var("gpu_cost")),
                Operator.LE, var("total_cost"), 4, "cpu + gpu <= total_cost",
            ),
        ],
        expected_result=CheckResult.UNSAT,
        expected_minimal_core_signatures={
            ("bound", "total_cost", "<=", "15000"),
            ("bound", "cpu_cost", ">=", "6000"),
            ("bound", "gpu_cost", ">=", "10000"),
            ("relation", "cpu_cost + gpu_cost", "<=", "total_cost"),
        },
    ),
    ConflictCase(
        name="hardware_satisfiable",
        domain="hardware",
        constraints=[
            _bound(var("total_cost"), Operator.LE, const(15000), 1, "Total cost must stay under 15k"),
            _bound(var("cpu_cost"), Operator.GE, const(6000), 2, "CPU costs at least 6k"),
            _bound(var("gpu_cost"), Operator.GE, const(8000), 3, "GPU costs at least 8k"),
            _relation(
                add(var("cpu_cost"), var("gpu_cost")),
                Operator.LE, var("total_cost"), 4, "cpu + gpu <= total_cost",
            ),
        ],
        expected_result=CheckResult.SAT,
    ),

    # -- Scheduling (transitive conflict through a RELATION) ----------------
    ConflictCase(
        name="scheduling_conflict",
        domain="scheduling",
        constraints=[
            _bound(var("project_a_end"), Operator.GE, const(10), 1, "Project A ends no earlier than day 10"),
            _bound(var("project_b_start"), Operator.LE, const(8), 2, "Project B must start by day 8"),
            _relation(
                var("project_b_start"), Operator.GE, var("project_a_end"),
                3, "Project B must start after Project A ends",
            ),
        ],
        expected_result=CheckResult.UNSAT,
        expected_minimal_core_signatures={
            ("bound", "project_a_end", ">=", "10"),
            ("bound", "project_b_start", "<=", "8"),
            ("relation", "project_b_start", ">=", "project_a_end"),
        },
    ),
    ConflictCase(
        name="scheduling_satisfiable",
        domain="scheduling",
        constraints=[
            _bound(var("project_a_end"), Operator.GE, const(10), 1, "Project A ends no earlier than day 10"),
            _bound(var("project_b_start"), Operator.LE, const(15), 2, "Project B must start by day 15"),
            _relation(
                var("project_b_start"), Operator.GE, var("project_a_end"),
                3, "Project B must start after Project A ends",
            ),
        ],
        expected_result=CheckResult.SAT,
    ),
]
