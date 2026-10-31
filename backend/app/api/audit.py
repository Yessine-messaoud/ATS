"""Read-only access to the audit log. Companies see their own entries; platform admins see all."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select

from app.db import AuditLogRecord, Role, UserRecord

from .deps import DbSession, StaffScope, get_scope
from .schemas import AuditEntryOut

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(get_scope)])


@router.get("")
def list_audit_entries(
    db: DbSession,
    scope: StaffScope,
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
    if scope.organization_id is not None:
        query = query.where(AuditLogRecord.organization_id == scope.organization_id)
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
    entries = list(db.scalars(query))
    names = staff_names(db, entries)
    return [
        AuditEntryOut(
            id=e.id,
            created_at=e.created_at,
            actor=e.actor,
            actor_name=names.get(e.actor),
            action=e.action,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            details=e.details,
        )
        for e in entries
    ]


def staff_names(db: DbSession, entries: list[AuditLogRecord]) -> dict[str, str]:
    """Names of the staff members behind `user:<id>` actors (candidates stay anonymous in the log)."""
    ids = {uuid.UUID(e.actor[5:45]) for e in entries if e.actor.startswith("user:") and len(e.actor) >= 41}
    query = select(UserRecord).where(UserRecord.id.in_(ids), UserRecord.role != Role.CANDIDATE)
    users = list(db.scalars(query)) if ids else []
    return {
        actor: f"{user.full_name}{suffix}"
        for user in users
        for actor, suffix in ((user.actor, ""), (f"{user.actor} via assistant", " (assistant)"))
    }
