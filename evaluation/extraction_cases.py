"""
Extraction evaluation cases: synthetic mini-conversations across budgeting,
scheduling, and hardware-configuration domains.

Each case lists every turn to feed the Extractor IN ORDER (earlier turns
often exist purely to set up state for a later revision/retraction turn --
e.g. you can't meaningfully test "revise the budget" without first stating
a budget). Every turn has an expected outcome kind, and ADD/REVISE turns
additionally specify an expected constraint "signature"
(kind, lhs_str, operator, rhs_str) that doesn't depend on auto-generated
ids, so cases remain stable regardless of global id-counter state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from constrainai.extraction import OutcomeKind

Signature = Tuple[str, str, str, str]  # (kind, lhs_str, operator, rhs_str)


@dataclass
class ExtractionCase:
    name: str
    domain: str
    turns: List[str]
    expected_kinds: List[OutcomeKind]
    expected_signatures: List[Optional[Signature]] = field(default_factory=list)

    def __post_init__(self):
        assert len(self.turns) == len(self.expected_kinds), self.name
        if not self.expected_signatures:
            self.expected_signatures = [None] * len(self.turns)
        assert len(self.expected_signatures) == len(self.turns), self.name


EXTRACTION_CASES: List[ExtractionCase] = [
    # -- Budgeting -----------------------------------------------------
    ExtractionCase(
        name="budgeting_basic_additions",
        domain="budgeting",
        turns=[
            "Budget must stay under ₹20k",
            "GPU costs at least ₹14k",
            "RAM costs at least ₹8k",
            "Reserve ₹2k for storage",
        ],
        expected_kinds=[OutcomeKind.ADD] * 4,
        expected_signatures=[
            ("bound", "budget", "<=", "20000"),
            ("bound", "gpu_cost", ">=", "14000"),
            ("bound", "ram_cost", ">=", "8000"),
            ("bound", "storage_cost", ">=", "2000"),
        ],
    ),
    ExtractionCase(
        name="budgeting_revise_then_retract",
        domain="budgeting",
        turns=[
            "Budget must stay under ₹20k",
            "RAM costs at least ₹8k",
            "Actually increase budget to ₹27k",
            "Ignore my previous RAM requirement",
        ],
        expected_kinds=[
            OutcomeKind.ADD, OutcomeKind.ADD, OutcomeKind.REVISE, OutcomeKind.RETRACT,
        ],
        expected_signatures=[
            ("bound", "budget", "<=", "20000"),
            ("bound", "ram_cost", ">=", "8000"),
            ("bound", "budget", "<=", "27000"),
            None,
        ],
    ),
    ExtractionCase(
        name="budgeting_number_formats",
        domain="budgeting",
        turns=[
            "Budget must stay under 20,000",
            "GPU costs at least 1.5 lakh",
        ],
        expected_kinds=[OutcomeKind.ADD, OutcomeKind.ADD],
        expected_signatures=[
            ("bound", "budget", "<=", "20000"),
            ("bound", "gpu_cost", ">=", "150000"),
        ],
    ),
    ExtractionCase(
        name="budgeting_revise_without_prior_is_ambiguous",
        domain="budgeting",
        turns=["Actually increase budget to ₹27k"],
        expected_kinds=[OutcomeKind.AMBIGUOUS],
    ),
    ExtractionCase(
        name="budgeting_retract_without_prior_is_ambiguous",
        domain="budgeting",
        turns=["Ignore my previous RAM requirement"],
        expected_kinds=[OutcomeKind.AMBIGUOUS],
    ),
    ExtractionCase(
        name="budgeting_unrecognized_smalltalk",
        domain="budgeting",
        turns=["Thanks, that's helpful!"],
        expected_kinds=[OutcomeKind.UNRECOGNIZED],
    ),

    # -- Hardware configuration -----------------------------------------
    ExtractionCase(
        name="hardware_basic_additions",
        domain="hardware",
        turns=[
            "GPU costs at least ₹10k",
            "RAM costs at least ₹4k",
            "Budget must stay under ₹15k",
        ],
        expected_kinds=[OutcomeKind.ADD] * 3,
        expected_signatures=[
            ("bound", "gpu_cost", ">=", "10000"),
            ("bound", "ram_cost", ">=", "4000"),
            ("bound", "budget", "<=", "15000"),
        ],
    ),
    ExtractionCase(
        name="hardware_revise_gpu_requirement",
        domain="hardware",
        turns=[
            "GPU costs at least ₹10k",
            "Actually decrease GPU to ₹9k",
        ],
        expected_kinds=[OutcomeKind.ADD, OutcomeKind.REVISE],
        expected_signatures=[
            ("bound", "gpu_cost", ">=", "10000"),
            ("bound", "gpu_cost", ">=", "9000"),
        ],
    ),

    # -- Scheduling ------------------------------------------------------
    ExtractionCase(
        name="scheduling_after_relation",
        domain="scheduling",
        turns=["Project B must start after Project A ends"],
        expected_kinds=[OutcomeKind.ADD],
        expected_signatures=[
            ("relation", "project_b_start", ">=", "project_a_end"),
        ],
    ),
    ExtractionCase(
        name="scheduling_before_relation",
        domain="scheduling",
        turns=["Project A must finish before Project B starts"],
        expected_kinds=[OutcomeKind.ADD],
        expected_signatures=[
            ("relation", "project_a_end", "<=", "project_b_start"),
        ],
    ),
    ExtractionCase(
        name="scheduling_mixed_bound_and_relation",
        domain="scheduling",
        turns=[
            "Project A end must stay under 10",
            "Project B must start after Project A ends",
        ],
        expected_kinds=[OutcomeKind.ADD, OutcomeKind.ADD],
        expected_signatures=[
            ("bound", "project_a_end", "<=", "10"),
            ("relation", "project_b_start", ">=", "project_a_end"),
        ],
    ),
    ExtractionCase(
        name="scheduling_unresolvable_relation_is_unrecognized",
        domain="scheduling",
        turns=["The party starts after the concert"],
        expected_kinds=[OutcomeKind.UNRECOGNIZED],
    ),
]
