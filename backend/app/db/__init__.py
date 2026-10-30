"""Persistence layer: SQLAlchemy records and session management."""

from .base import Base
from .records import (
    AgentConversationRecord,
    ApplicationRecord,
    ApplicationStage,
    AuditLogRecord,
    CandidateRecord,
    CandidateSearchRecord,
    DocumentRecord,
    JobRecord,
    JobSearchRecord,
    MatchRecord,
    TaxonomyBroaderRecord,
    TaxonomySkillRecord,
)
from .session import get_engine, get_session

__all__ = [
    "AgentConversationRecord",
    "ApplicationRecord",
    "ApplicationStage",
    "AuditLogRecord",
    "Base",
    "CandidateRecord",
    "CandidateSearchRecord",
    "DocumentRecord",
    "JobRecord",
    "JobSearchRecord",
    "MatchRecord",
    "TaxonomyBroaderRecord",
    "TaxonomySkillRecord",
    "get_engine",
    "get_session",
]
