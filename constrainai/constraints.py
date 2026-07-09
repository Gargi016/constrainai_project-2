"""
Constraint IR for ConstrainAI.

A Constraint is a typed relation between two Expressions, plus provenance
(where it came from) and lifecycle metadata (is it still active, was it
superseded by a later statement, was it explicitly retracted).

This module intentionally keeps semantic value ("is this SAT") entirely out
of the constraint object. Constraints are pure data; the Z3 compiler
(compiler.py) is the only place that gives them logical meaning.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from constrainai.expressions import Expression


class ConstraintKind(str, Enum):
    BOUND = "bound"          # x <= k, x >= k, etc. against a variable or linear expr
    EQUALITY = "equality"    # x == y
    RELATION = "relation"    # general relation between two linear expressions
    DEPENDENCY = "dependency"  # a requires b (implication)
    EXCLUSION = "exclusion"    # a excludes b
    MEMBERSHIP = "membership"  # x in {values}


class Operator(str, Enum):
    LE = "<="
    GE = ">="
    EQ = "=="
    NE = "!="
    REQUIRES = "requires"
    EXCLUDES = "excludes"
    IN = "in"


class Hardness(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class ConstraintStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"


# Mutable counter state (not itertools.count) so it can be *inspected and
# advanced* without consuming a value -- needed by the persistence layer:
# after reloading a conversation's constraints from SQLite, the in-process
# counter must be pushed past the highest id seen in storage, or a freshly
# generated id could collide with one already on disk (e.g. process
# restarts with a conversation that already has c1..c20 persisted, and the
# next brand-new constraint would otherwise be generated as "c1" again).
_counter_state = {"next": 1}

_ID_PATTERN = re.compile(r"^c(\d+)$")


def next_constraint_id() -> str:
    """Generate a fresh, human-scannable constraint id, e.g. 'c1', 'c2', ..."""
    n = _counter_state["next"]
    _counter_state["next"] = n + 1
    return f"c{n}"


def ensure_counter_ahead_of(constraint_id: str) -> None:
    """
    Advance the global id counter so that future calls to
    `next_constraint_id()` cannot collide with `constraint_id` (typically
    one just loaded from persistent storage). No-op for ids that don't
    match the standard "cN" shape (e.g. externally supplied ids).
    """
    match = _ID_PATTERN.match(constraint_id)
    if not match:
        return
    n = int(match.group(1))
    if _counter_state["next"] <= n:
        _counter_state["next"] = n + 1


class Constraint(BaseModel):
    """
    A single typed constraint with full provenance.

    lhs OPERATOR rhs

    e.g.  lhs = Sum(gpu_cost, ram_cost, storage_cost), operator = LE, rhs = Var(budget)
    """

    id: str = Field(default_factory=next_constraint_id)
    kind: ConstraintKind
    lhs: Expression
    operator: Operator
    rhs: Expression

    # Provenance
    source_turn: int
    source_text: str

    # Confidence that extraction correctly parsed the user's intent, in [0, 1].
    confidence: float = 1.0

    # Solver semantics
    hardness: Hardness = Hardness.HARD
    priority: int = 0  # higher = more important; used for repair ranking among soft constraints

    # Lifecycle
    status: ConstraintStatus = ConstraintStatus.ACTIVE
    supersedes: Optional[str] = None  # id of constraint this one replaces, if any

    def variables(self) -> set[str]:
        return self.lhs.variables() | self.rhs.variables()

    def __str__(self) -> str:
        return f"{self.lhs} {self.operator.value} {self.rhs}"

    def describe(self) -> str:
        """Human-readable line including provenance, for explanations/UI."""
        tag = "" if self.status == ConstraintStatus.ACTIVE else f" [{self.status.value}]"
        return f"[{self.id}]{tag} {self} (from turn {self.source_turn}: \"{self.source_text}\")"
