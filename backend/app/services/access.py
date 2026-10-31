"""Who may see what. Each company sees its own jobs, the candidates it uploaded, the people who applied to its jobs,
and portal candidates who opened their profile to all companies. Platform admins see everything.

Records outside the scope are reported as "not found", never as "forbidden", so that ids cannot be probed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, or_, select, true
from sqlalchemy.orm import Session

from app.db import ApplicationRecord, CandidateRecord, JobRecord, Role, UserRecord


def candidates_visible_to(organization_id: uuid.UUID | None) -> ColumnElement[bool]:
    """Candidates a company may see and rank. None means no company restriction (admins, internal services)."""
    if organization_id is None:
        return true()
    applied = (
        select(ApplicationRecord.candidate_id)
        .join(JobRecord, JobRecord.id == ApplicationRecord.job_id)
        .where(JobRecord.organization_id == organization_id)
    )
    return or_(
        CandidateRecord.organization_id == organization_id,
        CandidateRecord.id.in_(applied),
        and_(CandidateRecord.organization_id.is_(None), CandidateRecord.talent_pool_consent.is_(True)),
    )


def jobs_of(organization_id: uuid.UUID | None) -> ColumnElement[bool]:
    return true() if organization_id is None else JobRecord.organization_id == organization_id


@dataclass(frozen=True)
class Scope:
    """The signed-in staff member and the company whose data they work on (None for platform admins)."""

    user: UserRecord

    @property
    def organization_id(self) -> uuid.UUID | None:
        return None if self.user.role is Role.ADMIN else self.user.organization_id

    @property
    def is_admin(self) -> bool:
        return self.user.role is Role.ADMIN

    @property
    def actor(self) -> str:
        return self.user.actor

    def jobs(self) -> ColumnElement[bool]:
        return jobs_of(self.organization_id)

    def candidates(self) -> ColumnElement[bool]:
        return candidates_visible_to(self.organization_id)

    def job(self, db: Session, job_id: uuid.UUID) -> JobRecord | None:
        return db.scalar(select(JobRecord).where(JobRecord.id == job_id, self.jobs()))

    def candidate(self, db: Session, candidate_id: uuid.UUID) -> CandidateRecord | None:
        return db.scalar(select(CandidateRecord).where(CandidateRecord.id == candidate_id, self.candidates()))

    def application(self, db: Session, application_id: uuid.UUID) -> ApplicationRecord | None:
        return db.scalar(
            select(ApplicationRecord)
            .join(JobRecord, JobRecord.id == ApplicationRecord.job_id)
            .where(ApplicationRecord.id == application_id, self.jobs())
        )

    def manages(self, candidate: CandidateRecord) -> bool:
        """Whether this company may edit, merge, export or erase the candidate: only those it uploaded itself.

        Portal candidates own their profile; companies they applied to can read it and decide, not change it.
        """
        return self.is_admin or (
            candidate.organization_id is not None and candidate.organization_id == self.organization_id
        )
