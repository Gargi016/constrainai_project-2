"""Metric dataclasses for the evaluation harness. Pure data + arithmetic,
no solving logic -- runner.py does all the actual solving/extraction and
hands the raw per-case outcomes here to be aggregated."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


def safe_div(numerator: float, denominator: float) -> float:
    """Returns 0.0 for a 0/0 division instead of raising, since an empty
    denominator (e.g. 'no turns expected ADD/REVISE in this case set')
    means the metric is vacuously undefined, not a failure."""
    return numerator / denominator if denominator else 0.0


@dataclass
class ExtractionCaseResult:
    case_name: str
    domain: str
    turn_index: int
    turn_text: str
    expected_kind: str
    actual_kind: str
    expected_signature: Optional[tuple]
    actual_signature: Optional[tuple]

    @property
    def kind_correct(self) -> bool:
        return self.expected_kind == self.actual_kind

    @property
    def is_extraction_turn(self) -> bool:  # expected an ADD or REVISE
        return self.expected_kind in ("add", "revise")

    @property
    def predicted_extraction_turn(self) -> bool:  # actually produced ADD or REVISE
        return self.actual_kind in ("add", "revise")

    @property
    def extraction_correct(self) -> bool:
        return (
            self.is_extraction_turn
            and self.predicted_extraction_turn
            and self.expected_signature == self.actual_signature
        )

    @property
    def is_revision_or_retraction_turn(self) -> bool:
        return self.expected_kind in ("revise", "retract")


@dataclass
class ExtractionMetrics:
    results: List[ExtractionCaseResult] = field(default_factory=list)

    @property
    def total_turns(self) -> int:
        return len(self.results)

    @property
    def kind_accuracy(self) -> float:
        return safe_div(sum(r.kind_correct for r in self.results), self.total_turns)

    @property
    def extraction_precision(self) -> float:
        predicted = [r for r in self.results if r.predicted_extraction_turn]
        correct = [r for r in predicted if r.extraction_correct]
        return safe_div(len(correct), len(predicted))

    @property
    def extraction_recall(self) -> float:
        expected = [r for r in self.results if r.is_extraction_turn]
        correct = [r for r in expected if r.extraction_correct]
        return safe_div(len(correct), len(expected))

    @property
    def revision_retraction_accuracy(self) -> float:
        relevant = [r for r in self.results if r.is_revision_or_retraction_turn]
        correct = [r for r in relevant if r.kind_correct]
        return safe_div(len(correct), len(relevant))


@dataclass
class ConflictCaseResult:
    case_name: str
    domain: str
    expected_result: str
    actual_result: str
    predicted_minimal_core: Optional[set] = None
    expected_minimal_core: Optional[set] = None
    shrink_solver_calls: Optional[int] = None
    repair_count: int = 0
    repairs_all_verified: bool = True

    @property
    def sat_unsat_correct(self) -> bool:
        return self.expected_result == self.actual_result

    @property
    def is_unsat_case(self) -> bool:
        return self.expected_result == "unsat"

    @property
    def exact_conflict_match(self) -> Optional[bool]:
        if not self.is_unsat_case or self.predicted_minimal_core is None:
            return None
        return self.predicted_minimal_core == self.expected_minimal_core

    @property
    def conflict_precision(self) -> Optional[float]:
        if not self.is_unsat_case or self.predicted_minimal_core is None:
            return None
        if not self.predicted_minimal_core:
            return 0.0
        overlap = self.predicted_minimal_core & self.expected_minimal_core
        return len(overlap) / len(self.predicted_minimal_core)

    @property
    def conflict_recall(self) -> Optional[float]:
        if not self.is_unsat_case or self.predicted_minimal_core is None:
            return None
        if not self.expected_minimal_core:
            return 0.0
        overlap = self.predicted_minimal_core & self.expected_minimal_core
        return len(overlap) / len(self.expected_minimal_core)


@dataclass
class ConflictMetrics:
    results: List[ConflictCaseResult] = field(default_factory=list)

    @property
    def total_cases(self) -> int:
        return len(self.results)

    @property
    def sat_unsat_accuracy(self) -> float:
        return safe_div(sum(r.sat_unsat_correct for r in self.results), self.total_cases)

    @property
    def _unsat_results(self) -> List[ConflictCaseResult]:
        return [r for r in self.results if r.is_unsat_case]

    @property
    def exact_conflict_match_rate(self) -> float:
        unsat = self._unsat_results
        matches = [r for r in unsat if r.exact_conflict_match]
        return safe_div(len(matches), len(unsat))

    @property
    def avg_conflict_precision(self) -> float:
        unsat = [r for r in self._unsat_results if r.conflict_precision is not None]
        return safe_div(sum(r.conflict_precision for r in unsat), len(unsat))

    @property
    def avg_conflict_recall(self) -> float:
        unsat = [r for r in self._unsat_results if r.conflict_recall is not None]
        return safe_div(sum(r.conflict_recall for r in unsat), len(unsat))

    @property
    def avg_shrink_solver_calls(self) -> float:
        unsat = [r for r in self._unsat_results if r.shrink_solver_calls is not None]
        return safe_div(sum(r.shrink_solver_calls for r in unsat), len(unsat))

    @property
    def repair_validity_rate(self) -> float:
        unsat = [r for r in self._unsat_results if r.repair_count > 0]
        valid = [r for r in unsat if r.repairs_all_verified]
        return safe_div(len(valid), len(unsat))


@dataclass
class LatencyBenchmark:
    sizes: List[int] = field(default_factory=list)
    times_seconds: List[float] = field(default_factory=list)


@dataclass
class EvaluationReport:
    extraction: ExtractionMetrics
    conflict: ConflictMetrics
    latency: LatencyBenchmark
