"""Read-only access to the audit log."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import or_, select

from app.db import AuditLogRecord

from .deps import DbSession
from .schemas import AuditEntryOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit_entries(
    db: DbSession,
    entity_id: Annotated[uuid.UUID | None, Query(description="Entries about this record or naming it.")] = None,
    action: Annotated[
        str | None, Query(max_length=64, description="Exact action, or a prefix ending with '.'.")
    ] = None,
    actor: Annotated[str | None, Query(max_length=64)] = None,
    before: Annotated[datetime | None, Query(description="Only entries older than this (paging).")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AuditEntryOut]:
    """Most recent first. Decisions, AI outputs, corrections and privacy operations are all recorded here."""
    query = select(AuditLogRecord).order_by(AuditLogRecord.created_at.desc(), AuditLogRecord.id).limit(limit)
    if entity_id is not None:
        text_id = str(entity_id)
        query = query.where(
            or_(
                AuditLogRecord.entity_id == entity_id,
                AuditLogRecord.details["candidate_id"].astext == text_id,
                AuditLogRecord.details["job_id"].astext == text_id,
                AuditLogRecord.details["merged_id"].astext == text_id,
            )
        )
    if action:
        query = query.where(
            AuditLogRecord.action.startswith(action) if action.endswith(".") else AuditLogRecord.action == action
        )
    if actor:
        query = query.where(AuditLogRecord.actor == actor)
    if before is not None:
        query = query.where(AuditLogRecord.created_at < before)
    return [
        AuditEntryOut(
            id=e.id,
            created_at=e.created_at,
            actor=e.actor,
            action=e.action,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            details=e.details,
        )
        for e in db.scalars(query)
    ]
