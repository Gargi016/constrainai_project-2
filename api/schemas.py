"""Pydantic request schemas for the ConstrainAI API. Response bodies mostly
return the core IR types (Constraint, etc.) directly or plain dicts built
from them, rather than duplicating shapes here -- see api/main.py."""

from typing import List, Optional

from pydantic import BaseModel, field_validator


class TurnRequest(BaseModel):
    text: str


class RetractRequest(BaseModel):
    # Reserved for future fields (e.g. an optional reason); empty body is
    # also accepted by the retract endpoint since the constraint id is a
    # path parameter.
    pass


class RelationConstraintRequest(BaseModel):
    """
    Directly specifies a cross-variable RELATION constraint, e.g.
    "gpu_cost + ram_cost + storage_cost <= budget" or
    "project_b_start >= project_a_end". This bypasses NL extraction (which
    in this MVP only produces single-variable BOUND constraints, plus the
    "before"/"after" scheduling pattern) -- it's the typed-IR entry point
    for everything else RELATION constraints can express.

    lhs_variables / rhs_variables: one or more variable names. More than
    one on a side is compiled as their sum (e.g. lhs_variables=["gpu_cost",
    "ram_cost", "storage_cost"] becomes gpu_cost + ram_cost + storage_cost).
    """

    lhs_variables: List[str]
    operator: str  # "<=" or ">="
    rhs_variables: List[str]
    source_text: Optional[str] = None

    @field_validator("lhs_variables", "rhs_variables")
    @classmethod
    def _non_empty(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("must list at least one variable")
        return v

    @field_validator("operator")
    @classmethod
    def _valid_operator(cls, v: str) -> str:
        if v not in ("<=", ">="):
            raise ValueError('operator must be "<=" or ">="')
        return v
