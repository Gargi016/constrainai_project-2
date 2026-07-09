"""
Runs the evaluation case sets through the REAL pipeline (real Extractor,
real Z3 solver, real shrinking, real repair engine -- nothing here is
simulated) and aggregates the results into the metrics defined in
metrics.py.

    python3 -m evaluation.runner

prints a console report and, unless --no-write is given, also writes
evaluation/report.md.
"""

from __future__ import annotations

import sys
import time
from typing import List

from constrainai.constraints import ConstraintKind, Hardness, Operator
from constrainai.expressions import const, var
from constrainai.extraction import Extractor
from constrainai.repair import suggest_repairs
from constrainai.shrink import shrink_to_subset_minimal
from constrainai.solver import CheckResult, check_constraints
from constrainai.store import ConstraintStore

from evaluation.conflict_cases import CONFLICT_CASES, signature
from evaluation.extraction_cases import EXTRACTION_CASES
from evaluation.metrics import (
    ConflictCaseResult,
    ConflictMetrics,
    EvaluationReport,
    ExtractionCaseResult,
    ExtractionMetrics,
    LatencyBenchmark,
)


def run_extraction_cases(cases=EXTRACTION_CASES) -> ExtractionMetrics:
    metrics = ExtractionMetrics()
    for case in cases:
        store = ConstraintStore()
        extractor = Extractor()
        for i, text in enumerate(case.turns):
            outcome = extractor.process_turn(text, i + 1, store)
            actual_signature = None
            if outcome.constraint is not None:
                c = outcome.constraint
                actual_signature = (c.kind.value, str(c.lhs), c.operator.value, str(c.rhs))
            metrics.results.append(ExtractionCaseResult(
                case_name=case.name,
                domain=case.domain,
                turn_index=i + 1,
                turn_text=text,
                expected_kind=case.expected_kinds[i].value,
                actual_kind=outcome.kind.value,
                expected_signature=case.expected_signatures[i],
                actual_signature=actual_signature,
            ))
    return metrics


def run_conflict_cases(cases=CONFLICT_CASES) -> ConflictMetrics:
    metrics = ConflictMetrics()
    for case in cases:
        report = check_constraints(case.constraints)

        predicted_core = None
        solver_calls = None
        repair_count = 0
        repairs_all_verified = True

        if report.result == CheckResult.UNSAT:
            shrunk = shrink_to_subset_minimal(case.constraints)
            solver_calls = shrunk.solver_calls
            predicted_core = {signature(c) for c in shrunk.minimal_core}

            repairs = suggest_repairs(shrunk.minimal_core, full_active_set=case.constraints)
            repair_count = len(repairs)
            repairs_all_verified = all(r.verified_sat for r in repairs)

        metrics.results.append(ConflictCaseResult(
            case_name=case.name,
            domain=case.domain,
            expected_result=case.expected_result.value,
            actual_result=report.result.value,
            predicted_minimal_core=predicted_core,
            expected_minimal_core=case.expected_minimal_core_signatures,
            shrink_solver_calls=solver_calls,
            repair_count=repair_count,
            repairs_all_verified=repairs_all_verified,
        ))
    return metrics


def benchmark_solver_latency(sizes: List[int] = None) -> LatencyBenchmark:
    """
    Measures wall-clock SAT-check time for increasingly large, mutually
    independent constraint sets (N unrelated bound constraints, so the
    check is always SAT and any growth in time reflects compilation +
    solving overhead vs. constraint count, not case difficulty).
    """
    if sizes is None:
        sizes = [10, 50, 100, 250, 500]

    times: List[float] = []
    for n in sizes:
        constraints = [
            _bound_i(i) for i in range(n)
        ]
        start = time.perf_counter()
        check_constraints(constraints)
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    return LatencyBenchmark(sizes=sizes, times_seconds=times)


def _bound_i(i: int):
    from constrainai.constraints import Constraint
    return Constraint(
        kind=ConstraintKind.BOUND,
        lhs=var(f"x{i}"),
        operator=Operator.GE,
        rhs=const(0),
        source_turn=1,
        source_text=f"x{i} >= 0",
    )


def run_all() -> EvaluationReport:
    return EvaluationReport(
        extraction=run_extraction_cases(),
        conflict=run_conflict_cases(),
        latency=benchmark_solver_latency(),
    )


def format_console_report(report: EvaluationReport) -> str:
    e, c, lat = report.extraction, report.conflict, report.latency
    lines = []
    lines.append("=== Extraction metrics ===")
    lines.append(f"  turns evaluated:              {e.total_turns}")
    lines.append(f"  per-turn kind accuracy:       {e.kind_accuracy:.1%}")
    lines.append(f"  extraction precision:         {e.extraction_precision:.1%}")
    lines.append(f"  extraction recall:            {e.extraction_recall:.1%}")
    lines.append(f"  revision/retraction accuracy: {e.revision_retraction_accuracy:.1%}")

    lines.append("\n=== Conflict / repair metrics ===")
    lines.append(f"  cases evaluated:              {c.total_cases}")
    lines.append(f"  SAT/UNSAT accuracy:           {c.sat_unsat_accuracy:.1%}")
    lines.append(f"  exact conflict-set match:     {c.exact_conflict_match_rate:.1%}")
    lines.append(f"  conflict precision (avg):    {c.avg_conflict_precision:.1%}")
    lines.append(f"  conflict recall (avg):       {c.avg_conflict_recall:.1%}")
    lines.append(f"  avg shrink solver calls:      {c.avg_shrink_solver_calls:.1f}")
    lines.append(f"  repair validity rate:         {c.repair_validity_rate:.1%}")

    lines.append("\n=== Solver latency vs constraint count ===")
    for n, t in zip(lat.sizes, lat.times_seconds):
        lines.append(f"  n={n:<5} {t*1000:.2f} ms")

    lines.append("\n=== Per-case detail (extraction) ===")
    for r in e.results:
        status = "OK" if r.kind_correct else "MISMATCH"
        lines.append(
            f"  [{status}] {r.case_name} turn {r.turn_index} ({r.domain}): "
            f'"{r.turn_text}" expected={r.expected_kind} actual={r.actual_kind}'
        )

    lines.append("\n=== Per-case detail (conflict) ===")
    for r in c.results:
        status = "OK" if r.sat_unsat_correct else "MISMATCH"
        extra = ""
        if r.is_unsat_case:
            extra = (
                f" exact_match={r.exact_conflict_match} "
                f"precision={r.conflict_precision:.2f} recall={r.conflict_recall:.2f} "
                f"repairs={r.repair_count} verified={r.repairs_all_verified}"
            )
        lines.append(
            f"  [{status}] {r.case_name} ({r.domain}): expected={r.expected_result} "
            f"actual={r.actual_result}{extra}"
        )

    return "\n".join(lines)


def format_markdown_report(report: EvaluationReport) -> str:
    e, c, lat = report.extraction, report.conflict, report.latency
    lines = ["# ConstrainAI Evaluation Report", ""]

    lines.append("## Extraction metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Turns evaluated | {e.total_turns} |")
    lines.append(f"| Per-turn kind accuracy | {e.kind_accuracy:.1%} |")
    lines.append(f"| Extraction precision | {e.extraction_precision:.1%} |")
    lines.append(f"| Extraction recall | {e.extraction_recall:.1%} |")
    lines.append(f"| Revision/retraction accuracy | {e.revision_retraction_accuracy:.1%} |")
    lines.append("")

    lines.append("## Conflict / repair metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Cases evaluated | {c.total_cases} |")
    lines.append(f"| SAT/UNSAT accuracy | {c.sat_unsat_accuracy:.1%} |")
    lines.append(f"| Exact conflict-set match rate | {c.exact_conflict_match_rate:.1%} |")
    lines.append(f"| Conflict precision (avg) | {c.avg_conflict_precision:.1%} |")
    lines.append(f"| Conflict recall (avg) | {c.avg_conflict_recall:.1%} |")
    lines.append(f"| Avg core-shrinking solver calls | {c.avg_shrink_solver_calls:.1f} |")
    lines.append(f"| Repair validity rate | {c.repair_validity_rate:.1%} |")
    lines.append("")

    lines.append("## Solver latency vs constraint count")
    lines.append("")
    lines.append("| N constraints | Time (ms) |")
    lines.append("|---|---|")
    for n, t in zip(lat.sizes, lat.times_seconds):
        lines.append(f"| {n} | {t*1000:.2f} |")
    lines.append("")

    lines.append("## Per-case detail: extraction")
    lines.append("")
    lines.append("| Case | Turn | Domain | Text | Expected | Actual | Match |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in e.results:
        lines.append(
            f"| {r.case_name} | {r.turn_index} | {r.domain} | {r.turn_text} | "
            f"{r.expected_kind} | {r.actual_kind} | {'✅' if r.kind_correct else '❌'} |"
        )
    lines.append("")

    lines.append("## Per-case detail: conflict")
    lines.append("")
    lines.append("| Case | Domain | Expected | Actual | Exact match | Precision | Recall | Repairs | Verified |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in c.results:
        lines.append(
            f"| {r.case_name} | {r.domain} | {r.expected_result} | {r.actual_result} | "
            f"{r.exact_conflict_match if r.is_unsat_case else '—'} | "
            f"{f'{r.conflict_precision:.2f}' if r.conflict_precision is not None else '—'} | "
            f"{f'{r.conflict_recall:.2f}' if r.conflict_recall is not None else '—'} | "
            f"{r.repair_count} | {r.repairs_all_verified if r.is_unsat_case else '—'} |"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    report = run_all()
    print(format_console_report(report))

    if "--no-write" not in sys.argv:
        out_path = "evaluation/report.md"
        with open(out_path, "w") as f:
            f.write(format_markdown_report(report))
        print(f"\nWrote {out_path}")
