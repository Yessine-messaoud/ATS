"""Tags audit entries with the company they belong to.

The auth dependency (or the background worker) calls `set_audit_scope` once per session; every audit entry flushed
afterwards without an explicit company gets that one. This keeps the many `AuditLogRecord(...)` call sites in the
services unchanged while guaranteeing that a company's log never mixes with another's.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from .records import AuditLogRecord

_KEY = "audit_organization_id"


def set_audit_scope(session: Session, organization_id: uuid.UUID | None) -> None:
    session.info[_KEY] = organization_id


@event.listens_for(Session, "before_flush")
def _tag_audit_entries(session: Session, _context: Any, _instances: Any) -> None:
    organization_id = session.info.get(_KEY)
    if organization_id is None:
        return
    for entry in session.new:
        if isinstance(entry, AuditLogRecord) and entry.organization_id is None:
            entry.organization_id = organization_id
