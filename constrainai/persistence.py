"""
SQLite persistence for ConstrainAI.

Each conversation gets its own logical partition (by `conversation_id`) of a
single `constraints` table. A constraint's `lhs`/`rhs` Expression trees are
stored as JSON text (via Pydantic's own `model_dump_json()` /
`model_validate()` round trip) rather than being decomposed into relational
columns -- the IR is recursive and open-ended (Sum/Diff/Neg/Scale nest
arbitrarily), so JSON-in-a-column is the simplest representation that's
still exactly reconstructible, and it's what Constraint.lhs/rhs already
serialize to/from natively as Pydantic models.

This module does NOT change ConstraintStore's in-memory behavior. It reads
a full conversation's history out of SQLite into a fresh in-memory
ConstraintStore (`load_store`), and writes a full snapshot of a store's
history back to SQLite (`save_store`). This "snapshot" approach (delete +
reinsert per conversation) is simple, correct, and cheap enough for MVP
conversation sizes; if this ever became a bottleneck, incremental
upsert-by-row would be the natural next step, using the same schema.
"""

from __future__ import annotations

import json
import os
from typing import List, Optional

from sqlalchemy import Column, Float, Integer, String, Text, UniqueConstraint, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from constrainai.constraints import Constraint, ensure_counter_ahead_of
from constrainai.store import ConstraintStore


class Base(DeclarativeBase):
    pass


class ConstraintRecord(Base):
    """
    One row per constraint, per conversation. `pk` is a plain surrogate key
    used purely to preserve insertion order on reload (constraint ids are
    unique *within* a conversation but this keeps things simple even if
    that were ever relaxed).
    """

    __tablename__ = "constraints"

    pk: int = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id: str = Column(String, nullable=False, index=True)
    constraint_id: str = Column(String, nullable=False)
    kind: str = Column(String, nullable=False)
    lhs_json: str = Column(Text, nullable=False)
    operator: str = Column(String, nullable=False)
    rhs_json: str = Column(Text, nullable=False)
    source_turn: int = Column(Integer, nullable=False)
    source_text: str = Column(Text, nullable=False)
    confidence: float = Column(Float, nullable=False, default=1.0)
    hardness: str = Column(String, nullable=False)
    priority: int = Column(Integer, nullable=False, default=0)
    status: str = Column(String, nullable=False)
    supersedes: Optional[str] = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("conversation_id", "constraint_id", name="uq_conversation_constraint"),
    )


DEFAULT_DB_PATH = os.environ.get("CONSTRAINAI_DB_PATH", "constrainai.db")

_engine = None
_SessionLocal = None


def get_engine(db_path: str = DEFAULT_DB_PATH):
    """
    Return a process-wide SQLAlchemy engine for `db_path`, creating tables
    on first use. Tests pass a distinct tmp-file path per test to keep
    persistence tests fully isolated from each other and from any real
    conversation data.
    """
    global _engine, _SessionLocal
    if _engine is None or str(_engine.url).replace("sqlite:///", "") != db_path:
        _engine = create_engine(f"sqlite:///{db_path}", future=True)
        Base.metadata.create_all(_engine)
        _SessionLocal = sessionmaker(bind=_engine, future=True)
    return _engine


def get_session(db_path: str = DEFAULT_DB_PATH) -> Session:
    get_engine(db_path)  # ensures _SessionLocal is initialized for this path
    return _SessionLocal()


def _record_to_constraint(rec: ConstraintRecord) -> Constraint:
    data = {
        "id": rec.constraint_id,
        "kind": rec.kind,
        "lhs": json.loads(rec.lhs_json),
        "operator": rec.operator,
        "rhs": json.loads(rec.rhs_json),
        "source_turn": rec.source_turn,
        "source_text": rec.source_text,
        "confidence": rec.confidence,
        "hardness": rec.hardness,
        "priority": rec.priority,
        "status": rec.status,
        "supersedes": rec.supersedes,
    }
    return Constraint.model_validate(data)


def _constraint_to_record(conversation_id: str, c: Constraint) -> ConstraintRecord:
    return ConstraintRecord(
        conversation_id=conversation_id,
        constraint_id=c.id,
        kind=c.kind.value,
        lhs_json=c.lhs.model_dump_json(),
        operator=c.operator.value,
        rhs_json=c.rhs.model_dump_json(),
        source_turn=c.source_turn,
        source_text=c.source_text,
        confidence=c.confidence,
        hardness=c.hardness.value,
        priority=c.priority,
        status=c.status.value,
        supersedes=c.supersedes,
    )


def load_store(session: Session, conversation_id: str) -> ConstraintStore:
    """
    Rebuild a ConstraintStore from every row persisted for
    `conversation_id`, in original insertion order. Also advances the
    global constraint-id counter past every id loaded, so that if this
    process goes on to mint brand-new constraints (in this or any other
    conversation), it can never generate an id that collides with one
    already on disk.
    """
    store = ConstraintStore()
    rows = session.execute(
        select(ConstraintRecord)
        .where(ConstraintRecord.conversation_id == conversation_id)
        .order_by(ConstraintRecord.pk)
    ).scalars().all()

    for rec in rows:
        constraint = _record_to_constraint(rec)
        ensure_counter_ahead_of(constraint.id)
        store.add(constraint)

    return store


def save_store(session: Session, conversation_id: str, store: ConstraintStore) -> None:
    """
    Persist the full current state of `store` for `conversation_id`.
    Replaces any previously stored rows for this conversation with a fresh
    snapshot reflecting every constraint's current status (active /
    superseded / retracted) -- simple and correct for MVP conversation
    sizes.
    """
    session.execute(delete(ConstraintRecord).where(ConstraintRecord.conversation_id == conversation_id))
    for c in store.all():
        session.add(_constraint_to_record(conversation_id, c))
    session.commit()


def list_conversation_ids(session: Session) -> List[str]:
    rows = session.execute(select(ConstraintRecord.conversation_id).distinct()).scalars().all()
    return sorted(set(rows))


def delete_conversation(session: Session, conversation_id: str) -> None:
    session.execute(delete(ConstraintRecord).where(ConstraintRecord.conversation_id == conversation_id))
    session.commit()
