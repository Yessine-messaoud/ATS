from __future__ import annotations

import uuid
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.model import AgentModel
from app.agent.runtime import NoPendingAction, decide, send_message, transcript
from app.agent.tools import ToolContext
from app.config import get_settings
from app.db import AgentConversationRecord
from app.providers import make_agent_model
from app.services.access import Scope

from .deps import AppSettings, DbSession, StaffScope, domain_errors, get_or_404, get_scope

router = APIRouter(prefix="/agent", tags=["assistant"], dependencies=[Depends(get_scope)])


@lru_cache
def get_agent_model() -> AgentModel:
    return make_agent_model(get_settings())


Model = Annotated[AgentModel, Depends(get_agent_model)]


class ConversationIn(BaseModel):
    blind: bool = False


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class Decision(BaseModel):
    tool_use_id: str
    approved: bool


class DecisionsIn(BaseModel):
    decisions: list[Decision] = Field(min_length=1)


class PendingActionOut(BaseModel):
    tool_use_id: str
    name: str
    summary: str


class ConversationOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    blind: bool
    transcript: list[dict[str, Any]]
    pending_actions: list[PendingActionOut]
    usage: dict[str, Any]

    @classmethod
    def from_record(cls, record: AgentConversationRecord) -> ConversationOut:
        actions = (record.pending or {}).get("actions", [])
        return cls(
            id=record.id,
            created_at=record.created_at,
            blind=record.blind,
            transcript=transcript(record),
            pending_actions=[
                PendingActionOut(**{k: a[k] for k in ("tool_use_id", "name", "summary")}) for a in actions
            ],
            usage=record.usage or {},
        )


def _context(db: DbSession, settings: AppSettings, scope: Scope, conversation: AgentConversationRecord) -> ToolContext:
    return ToolContext(
        db=db,
        scope=scope,
        blind=conversation.blind,
        full_scoring_limit=settings.full_scoring_limit,
        retrieval_k=settings.retrieval_k,
        consent_required=settings.require_talent_pool_consent,
    )


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
def create_conversation(body: ConversationIn, db: DbSession, scope: StaffScope) -> ConversationOut:
    conversation = AgentConversationRecord(blind=body.blind, messages=[], usage={}, user_id=scope.user.id)
    db.add(conversation)
    db.commit()
    return ConversationOut.from_record(conversation)


def _conversation(db: DbSession, scope: Scope, conversation_id: uuid.UUID) -> AgentConversationRecord:
    """Conversations are private to the staff member who started them."""
    query = select(AgentConversationRecord).where(
        AgentConversationRecord.id == conversation_id, AgentConversationRecord.user_id == scope.user.id
    )
    return get_or_404(lambda: db.scalar(query), "conversation")


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: uuid.UUID, db: DbSession, scope: StaffScope) -> ConversationOut:
    return ConversationOut.from_record(_conversation(db, scope, conversation_id))


@router.post("/conversations/{conversation_id}/messages")
def post_message(
    conversation_id: uuid.UUID, body: MessageIn, db: DbSession, model: Model, settings: AppSettings, scope: StaffScope
) -> ConversationOut:
    """Send a message. Pending actions not yet confirmed are treated as declined."""
    conversation = _conversation(db, scope, conversation_id)
    with domain_errors():
        send_message(db, model, _context(db, settings, scope, conversation), conversation, body.text)
    return ConversationOut.from_record(conversation)


@router.post("/conversations/{conversation_id}/decisions")
def post_decisions(
    conversation_id: uuid.UUID, body: DecisionsIn, db: DbSession, model: Model, settings: AppSettings, scope: StaffScope
) -> ConversationOut:
    """Confirm or decline the proposed actions; confirmed ones are executed, then the assistant continues."""
    conversation = _conversation(db, scope, conversation_id)
    try:
        with domain_errors():
            decide(
                db,
                model,
                _context(db, settings, scope, conversation),
                conversation,
                {d.tool_use_id: d.approved for d in body.decisions},
            )
    except NoPendingAction as exc:
        raise HTTPException(409, str(exc)) from exc
    return ConversationOut.from_record(conversation)
