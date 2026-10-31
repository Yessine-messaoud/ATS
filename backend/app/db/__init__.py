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
    IngestionTaskRecord,
    JobRecord,
    JobSearchRecord,
    MatchRecord,
    OrganizationRecord,
    OrganizationStatus,
    Role,
    SessionRecord,
    TaskStatus,
    TaxonomyBroaderRecord,
    TaxonomySkillRecord,
    UserRecord,
)
from .scope import set_audit_scope
from .session import get_engine, get_session, new_session

__all__ = [
    "AgentConversationRecord",
    "ApplicationRecord",
    "ApplicationStage",
    "AuditLogRecord",
    "Base",
    "CandidateRecord",
    "CandidateSearchRecord",
    "DocumentRecord",
    "IngestionTaskRecord",
    "JobRecord",
    "JobSearchRecord",
    "MatchRecord",
    "OrganizationRecord",
    "OrganizationStatus",
    "Role",
    "SessionRecord",
    "TaskStatus",
    "TaxonomyBroaderRecord",
    "TaxonomySkillRecord",
    "UserRecord",
    "get_engine",
    "get_session",
    "new_session",
    "set_audit_scope",
]
