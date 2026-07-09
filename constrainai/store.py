"""
In-memory Constraint Store for ConstrainAI.

Owns the authoritative list of Constraint objects and their lifecycle
(active / superseded / retracted). This module is the single place that
mutates constraint status, so the rest of the system (solver, unsat core,
repair) can always ask the store "what's active right now?" and get a
consistent answer.

Revision semantics:
    - add(constraint): appends a new ACTIVE constraint.
    - revise(old_id, new_constraint): marks old_id SUPERSEDED, adds
      new_constraint ACTIVE, and records the link via `supersedes`.
    - retract(id): marks a constraint RETRACTED. It no longer participates
      in solving but remains in history for provenance/audit.

The store does not itself decide whether an incoming natural-language
statement is an addition vs. a revision vs. a retraction -- that judgment
belongs to the revision-resolution layer (built on top of extraction).
The store just executes whatever lifecycle operation it's told to.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from constrainai.constraints import Constraint, ConstraintStatus


class ConstraintNotFound(KeyError):
    """Raised when an operation references a constraint id that doesn't exist."""


class ConstraintStore:
    def __init__(self) -> None:
        self._constraints: Dict[str, Constraint] = {}
        # Preserves insertion order for deterministic iteration / display.
        self._order: List[str] = []

    # -- basic CRUD -----------------------------------------------------

    def add(self, constraint: Constraint) -> Constraint:
        if constraint.id in self._constraints:
            raise ValueError(f"Constraint id {constraint.id!r} already exists in store")
        self._constraints[constraint.id] = constraint
        self._order.append(constraint.id)
        return constraint

    def get(self, constraint_id: str) -> Constraint:
        try:
            return self._constraints[constraint_id]
        except KeyError as exc:
            raise ConstraintNotFound(constraint_id) from exc

    def all(self) -> List[Constraint]:
        """All constraints ever added, in insertion order, regardless of status."""
        return [self._constraints[cid] for cid in self._order]

    def active(self) -> List[Constraint]:
        return [c for c in self.all() if c.status == ConstraintStatus.ACTIVE]

    def by_status(self, status: ConstraintStatus) -> List[Constraint]:
        return [c for c in self.all() if c.status == status]

    # -- lifecycle transitions -------------------------------------------

    def retract(self, constraint_id: str) -> Constraint:
        """Mark a constraint as explicitly retracted by the user."""
        c = self.get(constraint_id)
        c.status = ConstraintStatus.RETRACTED
        return c

    def supersede(self, constraint_id: str) -> Constraint:
        """Mark a constraint as superseded (replaced by a newer statement)."""
        c = self.get(constraint_id)
        c.status = ConstraintStatus.SUPERSEDED
        return c

    def revise(self, old_id: str, new_constraint: Constraint) -> Constraint:
        """
        Replace an existing constraint with a new one: the old constraint is
        marked SUPERSEDED and the new constraint is added ACTIVE, linked via
        `supersedes`.
        """
        self.supersede(old_id)
        new_constraint.supersedes = old_id
        return self.add(new_constraint)

    # -- convenience -------------------------------------------------------

    def find_active_on_variable(self, variable_name: str) -> List[Constraint]:
        """
        Active constraints that mention a given variable. Useful for revision
        resolution: "increase budget to 27000" needs to find prior active
        constraints on `budget` to supersede.
        """
        return [c for c in self.active() if variable_name in c.variables()]

    def clear(self) -> None:
        self._constraints.clear()
        self._order.clear()
