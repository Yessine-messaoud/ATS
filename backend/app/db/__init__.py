"""Persistence layer: SQLAlchemy records and session management."""

from .base import Base
from .records import (
    ApplicationRecord,
    ApplicationStage,
    AuditLogRecord,
    CandidateRecord,
    DocumentRecord,
    JobRecord,
    MatchRecord,
)
from .session import get_engine, get_session

__all__ = [
    "ApplicationRecord",
    "ApplicationStage",
    "AuditLogRecord",
    "Base",
    "CandidateRecord",
    "DocumentRecord",
    "JobRecord",
    "MatchRecord",
    "get_engine",
    "get_session",
]
