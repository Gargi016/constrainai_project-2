"""
Deterministic natural-language extraction for ConstrainAI.

Per the project spec: "Do not make reasoning dependent on paid LLM APIs.
Start with deterministic extraction for supported patterns." This module
is pure Python regex/rule-based parsing -- no model calls, fully
reproducible, and every failure mode (unrecognized phrasing, ambiguous
variable reference) is surfaced explicitly rather than guessed at.

Pipeline for a single user turn:

    raw text
      -> normalize (lowercase, strip currency symbols/commas for matching)
      -> classify: RETRACT | REVISE | ADD | AMBIGUOUS | UNRECOGNIZED
      -> (RETRACT)  find the single active bound constraint on the named
                    variable; if zero or more than one match, return
                    AMBIGUOUS instead of guessing (spec requirement #4).
      -> (REVISE)   find the single active bound constraint on the named
                    variable to reuse its operator (a "revision" only makes
                    sense in the context of an existing constraint on that
                    variable); if zero or more than one, AMBIGUOUS.
      -> (ADD)      build a brand new Constraint from the recognized
                    pattern; if the phrasing doesn't match any known
                    pattern, UNRECOGNIZED (never silently fabricated).

This module intentionally covers a SMALL, extensible set of patterns
sufficient for the spec's example conversation. Real coverage growth is
meant to happen by adding entries to VARIABLE_SYNONYMS and the pattern
lists, each with its own test -- not by loosening the matching logic to
"guess" more.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from constrainai.constraints import Constraint, ConstraintKind, Operator
from constrainai.expressions import const, var
from constrainai.store import ConstraintStore


# ---------------------------------------------------------------------------
# Vocabulary: surface-form synonyms -> canonical variable name.
# Longer / more specific phrases must be listed so they're matched before
# shorter ones when several could apply to the same text.
# ---------------------------------------------------------------------------

DEFAULT_VARIABLE_SYNONYMS: Dict[str, List[str]] = {
    "budget": ["budget"],
    "gpu_cost": ["gpu", "graphics card", "video card"],
    "ram_cost": ["ram", "memory"],
    "storage_cost": ["storage", "disk", "ssd", "hard drive"],
    "project_a_start": ["project a start", "project a's start", "start of project a"],
    "project_a_end": [
        "project a end", "project a's end", "end of project a",
        "project a finish", "project a complete",
    ],
    "project_b_start": ["project b start", "project b's start", "start of project b"],
    "project_b_end": [
        "project b end", "project b's end", "end of project b",
        "project b finish", "project b complete",
    ],
}


class OutcomeKind(str, Enum):
    ADD = "add"
    REVISE = "revise"
    RETRACT = "retract"
    AMBIGUOUS = "ambiguous"
    UNRECOGNIZED = "unrecognized"


@dataclass
class ExtractionOutcome:
    kind: OutcomeKind
    # For ADD: the new constraint to add.
    # For REVISE: the new constraint to add (old_constraint_id names what it supersedes).
    constraint: Optional[Constraint] = None
    # For REVISE / RETRACT: the id of the existing constraint being replaced/retracted.
    old_constraint_id: Optional[str] = None
    # Human-readable explanation, always populated -- especially important
    # for AMBIGUOUS/UNRECOGNIZED so the caller can surface it as a
    # clarification question rather than a silent no-op.
    message: str = ""


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = text.replace("₹", "")
    return text


_NUMBER_RE = re.compile(
    r"(?P<num>[\d][\d,]*(?:\.\d+)?)\s*(?P<suffix>k|lakh|lakhs|l)?", re.IGNORECASE
)


def _parse_number(text: str) -> Optional[float]:
    """
    Parse the first number in `text`, handling commas and k/lakh suffixes.
    Returns None if no number is found. Examples:
        "20k"        -> 20000.0
        "20,000"     -> 20000.0
        "2 lakh"     -> 200000.0
        "8000"       -> 8000.0
    """
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    raw = match.group("num").replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    suffix = (match.group("suffix") or "").lower()
    if suffix == "k":
        value *= 1_000
    elif suffix in ("lakh", "lakhs", "l"):
        value *= 100_000
    return value


def _phrase_pattern(phrase: str) -> re.Pattern:
    """
    Build a regex that matches `phrase`'s words in order, allowing at most
    one filler word between each pair (e.g. so the synonym phrase
    "project b start" also matches "project b must start" or "project b
    now starts"). Single-word phrases ("budget", "gpu") are unaffected.
    """
    words = phrase.split()
    joined = r"\s+(?:\S+\s+)?".join(re.escape(w) for w in words)
    return re.compile(joined)


def _find_variable(text: str, synonyms: Dict[str, List[str]]) -> Optional[str]:
    """
    Find the canonical variable name whose synonym list has the longest
    matching phrase in `text`. Longest-match-wins avoids e.g. "video card"
    losing to a shorter, unrelated substring match.
    """
    best: Optional[str] = None
    best_len = 0
    for canonical, phrases in synonyms.items():
        for phrase in phrases:
            if _phrase_pattern(phrase).search(text) and len(phrase) > best_len:
                best = canonical
                best_len = len(phrase)
    return best


# ---------------------------------------------------------------------------
# Pattern classifiers, tried in this order: RETRACT, REVISE, ADD.
# Order matters: "actually increase budget to 27k" must be classified as
# REVISE, not accidentally matched by a generic "increase" ADD pattern.
# ---------------------------------------------------------------------------

_RETRACT_KEYWORDS = [
    "ignore", "forget", "retract", "remove", "cancel", "drop", "no longer",
    "never mind", "scratch that",
]

_REVISE_VERBS = [
    "increase", "raise", "bump up", "decrease", "lower", "reduce",
    "change", "update", "set", "adjust", "revise",
]

_LE_PHRASES = [
    "must stay under", "should stay under", "stay under", "at most",
    "no more than", "under", "cap at", "capped at", "maximum of", "max of",
]
_GE_PHRASES = [
    "at least", "minimum of", "must be at least", "no less than", "over",
]
_EQ_PHRASES = ["exactly", "must equal", "equal to"]
_RESERVE_PHRASES = ["reserve"]  # "reserve X for VAR" -> VAR >= X


def _is_retraction(text: str) -> bool:
    return any(kw in text for kw in _RETRACT_KEYWORDS)


def _is_revision(text: str) -> bool:
    return any(verb in text for verb in _REVISE_VERBS) and _NUMBER_RE.search(text) is not None


class Extractor:
    """
    Stateless (per-call) deterministic extractor. Holds only the variable
    vocabulary; all mutation of constraint lifecycle happens in
    `process_turn`, which reads/writes the given ConstraintStore directly
    so revision/retraction can look up "what's currently active."
    """

    def __init__(self, variable_synonyms: Optional[Dict[str, List[str]]] = None):
        self.variable_synonyms = variable_synonyms or DEFAULT_VARIABLE_SYNONYMS

    # -- top-level entry point -------------------------------------------

    def process_turn(
        self, text: str, turn_number: int, store: ConstraintStore
    ) -> ExtractionOutcome:
        """
        Parse `text` and apply the resulting lifecycle operation (add /
        revise / retract) to `store`. Returns an ExtractionOutcome
        describing what happened (or why nothing could be determined).
        AMBIGUOUS and UNRECOGNIZED outcomes never mutate the store.
        """
        normalized = _normalize(text)

        if _is_retraction(normalized):
            return self._handle_retraction(text, normalized, turn_number, store)

        if _is_revision(normalized):
            return self._handle_revision(text, normalized, turn_number, store)

        relation_outcome = self._handle_relation(text, normalized, turn_number, store)
        if relation_outcome is not None:
            return relation_outcome

        return self._handle_addition(text, normalized, turn_number, store)

    # -- two-variable scheduling relation ("X after/before Y") -------------

    def _handle_relation(
        self, raw_text: str, text: str, turn_number: int, store: ConstraintStore
    ) -> Optional[ExtractionOutcome]:
        """
        Handles simple two-variable ordering statements like "Project B must
        start after Project A ends" (-> project_b_start >= project_a_end)
        or "Project A must finish before Project B starts" (-> project_a_end
        <= project_b_start). Returns None (not UNRECOGNIZED) if the text
        contains neither "after" nor "before", so callers can fall through
        to single-variable bound extraction instead.
        """
        if " after " in text:
            left_text, right_text = text.split(" after ", 1)
            operator = Operator.GE
        elif " before " in text:
            left_text, right_text = text.split(" before ", 1)
            operator = Operator.LE
        else:
            return None

        left_var = _find_variable(left_text, self.variable_synonyms)
        right_var = _find_variable(right_text, self.variable_synonyms)

        if left_var is None or right_var is None or left_var == right_var:
            return ExtractionOutcome(
                kind=OutcomeKind.UNRECOGNIZED,
                message=(
                    f'Turn {turn_number}: found an ordering phrase ("after"/"before") in '
                    f'"{raw_text}" but could not resolve two distinct known variables around it.'
                ),
            )

        new_constraint = Constraint(
            kind=ConstraintKind.RELATION,
            lhs=var(left_var),
            operator=operator,
            rhs=var(right_var),
            source_turn=turn_number,
            source_text=raw_text,
        )
        store.add(new_constraint)
        return ExtractionOutcome(
            kind=OutcomeKind.ADD,
            constraint=new_constraint,
            message=f'Turn {turn_number}: added [{new_constraint.id}] {new_constraint} (from "{raw_text}").',
        )

    # -- retraction --------------------------------------------------------

    def _handle_retraction(
        self, raw_text: str, text: str, turn_number: int, store: ConstraintStore
    ) -> ExtractionOutcome:
        variable = _find_variable(text, self.variable_synonyms)
        if variable is None:
            return ExtractionOutcome(
                kind=OutcomeKind.UNRECOGNIZED,
                message=(
                    f'Turn {turn_number}: recognized a retraction phrase in "{raw_text}" '
                    "but couldn't tell which requirement it refers to."
                ),
            )

        matches = [
            c for c in store.find_active_on_variable(variable)
            if c.kind == ConstraintKind.BOUND
        ]
        if len(matches) == 0:
            return ExtractionOutcome(
                kind=OutcomeKind.AMBIGUOUS,
                message=(
                    f'Turn {turn_number}: "{raw_text}" looks like a retraction for '
                    f"'{variable}', but there is no active requirement on it to retract."
                ),
            )
        if len(matches) > 1:
            ids = ", ".join(c.id for c in matches)
            return ExtractionOutcome(
                kind=OutcomeKind.AMBIGUOUS,
                message=(
                    f'Turn {turn_number}: "{raw_text}" could refer to more than one active '
                    f"requirement on '{variable}' ({ids}). Which one should be retracted?"
                ),
            )

        target = matches[0]
        store.retract(target.id)
        return ExtractionOutcome(
            kind=OutcomeKind.RETRACT,
            old_constraint_id=target.id,
            message=f'Turn {turn_number}: retracted [{target.id}] {target} (from "{raw_text}").',
        )

    # -- revision ------------------------------------------------------------

    def _handle_revision(
        self, raw_text: str, text: str, turn_number: int, store: ConstraintStore
    ) -> ExtractionOutcome:
        variable = _find_variable(text, self.variable_synonyms)
        value = _parse_number(text)

        if variable is None or value is None:
            return ExtractionOutcome(
                kind=OutcomeKind.UNRECOGNIZED,
                message=(
                    f'Turn {turn_number}: recognized a revision verb in "{raw_text}" but '
                    "couldn't identify both the target variable and the new value."
                ),
            )

        matches = [
            c for c in store.find_active_on_variable(variable)
            if c.kind == ConstraintKind.BOUND
        ]
        if len(matches) == 0:
            return ExtractionOutcome(
                kind=OutcomeKind.AMBIGUOUS,
                message=(
                    f'Turn {turn_number}: "{raw_text}" looks like a revision for '
                    f"'{variable}', but there is no existing active requirement on it to revise "
                    "(nothing to infer the comparison direction from)."
                ),
            )
        if len(matches) > 1:
            ids = ", ".join(c.id for c in matches)
            return ExtractionOutcome(
                kind=OutcomeKind.AMBIGUOUS,
                message=(
                    f'Turn {turn_number}: "{raw_text}" could be revising more than one active '
                    f"requirement on '{variable}' ({ids}). Which one should be updated?"
                ),
            )

        old = matches[0]
        new_constraint = Constraint(
            kind=ConstraintKind.BOUND,
            lhs=var(variable),
            operator=old.operator,  # revision reuses the prior comparison direction
            rhs=const(value),
            source_turn=turn_number,
            source_text=raw_text,
        )
        store.revise(old.id, new_constraint)
        return ExtractionOutcome(
            kind=OutcomeKind.REVISE,
            constraint=new_constraint,
            old_constraint_id=old.id,
            message=(
                f'Turn {turn_number}: revised [{old.id}] {old} -> '
                f"[{new_constraint.id}] {new_constraint} (from \"{raw_text}\")."
            ),
        )

    # -- addition ------------------------------------------------------------

    def _handle_addition(
        self, raw_text: str, text: str, turn_number: int, store: ConstraintStore
    ) -> ExtractionOutcome:
        variable = _find_variable(text, self.variable_synonyms)
        value = _parse_number(text)

        if variable is None or value is None:
            return ExtractionOutcome(
                kind=OutcomeKind.UNRECOGNIZED,
                message=(
                    f'Turn {turn_number}: could not extract a constraint from "{raw_text}" -- '
                    "no recognized variable and/or number found."
                ),
            )

        operator = self._infer_operator(text)
        if operator is None:
            return ExtractionOutcome(
                kind=OutcomeKind.UNRECOGNIZED,
                message=(
                    f'Turn {turn_number}: found variable "{variable}" and a number in '
                    f'"{raw_text}", but no recognized comparison phrase '
                    '(e.g. "at least", "under", "exactly").'
                ),
            )

        new_constraint = Constraint(
            kind=ConstraintKind.BOUND,
            lhs=var(variable),
            operator=operator,
            rhs=const(value),
            source_turn=turn_number,
            source_text=raw_text,
        )
        store.add(new_constraint)
        return ExtractionOutcome(
            kind=OutcomeKind.ADD,
            constraint=new_constraint,
            message=f'Turn {turn_number}: added [{new_constraint.id}] {new_constraint} (from "{raw_text}").',
        )

    @staticmethod
    def _infer_operator(text: str) -> Optional[Operator]:
        # "reserve X for VAR" always means VAR >= X regardless of other
        # phrases that might also appear, so check it first.
        if any(p in text for p in _RESERVE_PHRASES):
            return Operator.GE
        if any(p in text for p in _EQ_PHRASES):
            return Operator.EQ
        if any(p in text for p in _LE_PHRASES):
            return Operator.LE
        if any(p in text for p in _GE_PHRASES):
            return Operator.GE
        if "costs" in text and any(p in text for p in _GE_PHRASES):
            return Operator.GE
        return None
