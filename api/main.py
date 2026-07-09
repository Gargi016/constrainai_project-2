"""
FastAPI service for ConstrainAI.

Run locally with:
    uvicorn api.main:app --reload

Every endpoint is a thin HTTP wrapper around the deterministic reasoning
core (constrainai/*): no reasoning logic lives in this file. Each request
loads the relevant conversation's constraints from SQLite
(`persistence.load_store`), applies the requested operation using the same
`ConstraintStore` / `Extractor` / solver / repair modules exercised by the
core test suite, then persists the result back
(`persistence.save_store`) before responding.

Endpoints
---------
POST   /conversations/{conversation_id}/turns
       Body: {"text": "..."}. Runs deterministic NL extraction against the
       conversation's current store. Returns the extraction outcome plus
       the resulting SAT/UNSAT status.

POST   /conversations/{conversation_id}/constraints/relation
       Body: {"lhs_variables": [...], "operator": "<="|">=", "rhs_variables": [...],
       "source_text": "..."}. Adds a cross-variable RELATION constraint
       directly (bypassing NL extraction, which doesn't produce these in
       this MVP beyond the "before"/"after" scheduling pattern). Multiple
       variables on a side are summed.

GET    /conversations/{conversation_id}/constraints?status=active|all
       Lists constraints (default: only active).

GET    /conversations/{conversation_id}/check
       SAT/UNSAT check. On UNSAT, includes the raw (non-minimal) unsat core
       AND the independently-verified subset-minimal core.

GET    /conversations/{conversation_id}/repairs
       On UNSAT, returns solver-verified repair candidates (see
       constrainai/repair.py). Empty list if SAT or if no adjustable bound
       could be found/verified.

POST   /conversations/{conversation_id}/constraints/{constraint_id}/retract
       Manually retract a specific constraint (e.g. a UI "x" button next to
       a constraint in the sidebar), independent of NL extraction.

GET    /conversations
       Lists known conversation ids.

DELETE /conversations/{conversation_id}
       Deletes all persisted constraints for a conversation.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from constrainai import persistence
from constrainai.constraints import Constraint, ConstraintKind, ConstraintStatus, Operator
from constrainai.expressions import Sum, Var
from constrainai.extraction import Extractor
from constrainai.repair import suggest_repairs
from constrainai.shrink import shrink_to_subset_minimal, verify_subset_minimal
from constrainai.solver import CheckResult, check_constraints
from constrainai.store import ConstraintNotFound
from constrainai.unsat_core import extract_unsat_core

from api.schemas import RelationConstraintRequest, TurnRequest

app = FastAPI(
    title="ConstrainAI",
    description="Conversational Constraint Solving with Minimal Conflict Isolation and Repair",
    version="0.1.0",
)

# Local-dev CORS: allows the Next.js frontend (typically localhost:3000) to
# call this API (typically localhost:8000) from the browser. Tighten
# allow_origins before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_extractor = Extractor()


def get_db() -> Session:
    session = persistence.get_session()
    try:
        yield session
    finally:
        session.close()


def _next_turn_number(store) -> int:
    turns = [c.source_turn for c in store.all()]
    return (max(turns) + 1) if turns else 1


def _sat_status_payload(active: List[Constraint]) -> dict:
    report = check_constraints(active)
    payload = {"result": report.result.value}
    if report.result == CheckResult.SAT:
        payload["model"] = report.model
    return payload


@app.post("/conversations/{conversation_id}/turns")
def post_turn(conversation_id: str, body: TurnRequest, db: Session = Depends(get_db)):
    store = persistence.load_store(db, conversation_id)
    turn_number = _next_turn_number(store)

    outcome = _extractor.process_turn(body.text, turn_number, store)
    persistence.save_store(db, conversation_id, store)

    active = store.active()
    return {
        "outcome": {
            "kind": outcome.kind.value,
            "message": outcome.message,
            "constraint_id": outcome.constraint.id if outcome.constraint else None,
            "old_constraint_id": outcome.old_constraint_id,
        },
        "turn_number": turn_number,
        "active_constraint_count": len(active),
        "sat_status": _sat_status_payload(active),
    }


@app.post("/conversations/{conversation_id}/constraints/relation")
def post_relation_constraint(
    conversation_id: str, body: RelationConstraintRequest, db: Session = Depends(get_db)
):
    def build_side(names: list) -> Var | Sum:
        variables = [Var(name=n) for n in names]
        return variables[0] if len(variables) == 1 else Sum(terms=variables)

    lhs = build_side(body.lhs_variables)
    rhs = build_side(body.rhs_variables)

    store = persistence.load_store(db, conversation_id)
    turn_number = _next_turn_number(store)

    default_text = f"{'+'.join(body.lhs_variables)} {body.operator} {'+'.join(body.rhs_variables)}"
    constraint = Constraint(
        kind=ConstraintKind.RELATION,
        lhs=lhs,
        operator=Operator(body.operator),
        rhs=rhs,
        source_turn=turn_number,
        source_text=body.source_text or default_text,
    )
    store.add(constraint)
    persistence.save_store(db, conversation_id, store)

    active = store.active()
    return {
        "constraint": constraint.model_dump(),
        "turn_number": turn_number,
        "active_constraint_count": len(active),
        "sat_status": _sat_status_payload(active),
    }


@app.get("/conversations/{conversation_id}/constraints", response_model=List[Constraint])
def get_constraints(
    conversation_id: str, status: Optional[str] = "active", db: Session = Depends(get_db)
):
    store = persistence.load_store(db, conversation_id)
    if status == "all":
        return store.all()
    try:
        status_enum = ConstraintStatus(status)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status {status!r}; expected 'all', 'active', 'superseded', or 'retracted'.",
        )
    return store.by_status(status_enum)


@app.get("/conversations/{conversation_id}/check")
def get_check(conversation_id: str, db: Session = Depends(get_db)):
    store = persistence.load_store(db, conversation_id)
    active = store.active()
    report = check_constraints(active)

    result = {"result": report.result.value}
    if report.result == CheckResult.SAT:
        result["model"] = report.model
        return result

    if report.result == CheckResult.UNSAT:
        raw = extract_unsat_core(active)
        shrunk = shrink_to_subset_minimal(active)
        verified = verify_subset_minimal(active, shrunk.minimal_core)
        result["raw_core"] = [c.model_dump() for c in raw.raw_core] if raw else []
        result["minimal_core"] = [c.model_dump() for c in shrunk.minimal_core]
        result["minimal_core_verified"] = verified
        return result

    return result  # UNKNOWN, surfaced as-is rather than hidden


@app.get("/conversations/{conversation_id}/repairs")
def get_repairs(conversation_id: str, db: Session = Depends(get_db)):
    store = persistence.load_store(db, conversation_id)
    active = store.active()
    report = check_constraints(active)

    if report.result != CheckResult.UNSAT:
        return {"repairs_needed": False, "repairs": []}

    shrunk = shrink_to_subset_minimal(active)
    candidates = suggest_repairs(shrunk.minimal_core, full_active_set=active)
    return {
        "repairs_needed": True,
        "repairs": [
            {
                "constraint_id": c.constraint.id,
                "variable_name": c.variable_name,
                "original_value": c.original_value,
                "new_value": c.new_value,
                "delta": c.delta,
                "direction": c.direction,
                "verified_sat": c.verified_sat,
                "description": c.describe(),
            }
            for c in candidates
        ],
    }


@app.post("/conversations/{conversation_id}/constraints/{constraint_id}/retract")
def retract_constraint(conversation_id: str, constraint_id: str, db: Session = Depends(get_db)):
    store = persistence.load_store(db, conversation_id)
    try:
        constraint = store.retract(constraint_id)
    except ConstraintNotFound:
        raise HTTPException(status_code=404, detail=f"No constraint {constraint_id!r} in this conversation.")

    persistence.save_store(db, conversation_id, store)
    active = store.active()
    return {
        "retracted_constraint_id": constraint.id,
        "active_constraint_count": len(active),
        "sat_status": _sat_status_payload(active),
    }


@app.get("/conversations")
def list_conversations(db: Session = Depends(get_db)):
    return {"conversation_ids": persistence.list_conversation_ids(db)}


@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    persistence.delete_conversation(db, conversation_id)
    return {"deleted": conversation_id}
