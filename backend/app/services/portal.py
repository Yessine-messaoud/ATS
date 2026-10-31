"""Candidate portal: the public job board, applying with a CV, following applications, owning one's profile.

Candidates never see scores, rankings or recruiter notes: only where their application stands. CVs sent through the
portal are read in the background (see app.services.tasks), so applying takes a second, not a minute.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import (
    ApplicationRecord,
    ApplicationStage,
    CandidateRecord,
    IngestionTaskRecord,
    JobRecord,
    OrganizationRecord,
    OrganizationStatus,
    TaskStatus,
    UserRecord,
    set_audit_scope,
)
from app.models import CandidateProfile
from app.models.common import Evidenced
from app.services.pipeline import AlreadyInPipeline, add_to_pipeline, move_application
from app.services.profiles import correct_candidate_profile

# What a candidate sees for each pipeline stage. Interview and offer are shown: the candidate is told about them anyway.
CANDIDATE_STATUS: dict[ApplicationStage, tuple[str, str]] = {
    ApplicationStage.NEW: ("received", "Received"),
    ApplicationStage.SCREENING: ("in_review", "In review"),
    ApplicationStage.INTERVIEW: ("interview", "Interview"),
    ApplicationStage.OFFER: ("offer", "Offer"),
    ApplicationStage.HIRED: ("hired", "Hired"),
    ApplicationStage.REJECTED: ("not_selected", "Not selected"),
    ApplicationStage.WITHDRAWN: ("withdrawn", "Withdrawn"),
}
FINAL_STAGES = {ApplicationStage.HIRED, ApplicationStage.REJECTED, ApplicationStage.WITHDRAWN}


class PortalError(ValueError):
    """A refused portal operation; the message is safe to show to the candidate."""


def public_jobs_query() -> Select[JobRecord]:
    """Open jobs of approved companies: what the careers page lists."""
    return (
        select(JobRecord)
        .join(OrganizationRecord, OrganizationRecord.id == JobRecord.organization_id)
        .where(JobRecord.status == "open", OrganizationRecord.status == OrganizationStatus.ACTIVE)
        .order_by(JobRecord.created_at.desc())
    )


def public_job(db: Session, job_id: uuid.UUID) -> JobRecord | None:
    return db.scalar(public_jobs_query().where(JobRecord.id == job_id))


def candidate_of(db: Session, user: UserRecord) -> CandidateRecord | None:
    return db.scalar(select(CandidateRecord).where(CandidateRecord.user_id == user.id))


def pending_tasks(db: Session, user: UserRecord) -> list[IngestionTaskRecord]:
    return list(
        db.scalars(
            select(IngestionTaskRecord)
            .where(IngestionTaskRecord.user_id == user.id)
            .order_by(IngestionTaskRecord.created_at.desc())
            .limit(20)
        )
    )


def queue_cv(
    db: Session,
    settings: Settings,
    user: UserRecord,
    *,
    data: bytes,
    filename: str | None,
    job: JobRecord | None,
    talent_pool_consent: bool | None,
) -> IngestionTaskRecord:
    """Store the CV (encrypted) for the background worker; the application is created once it has been read."""
    if not data:
        raise PortalError("the file is empty")
    if len(data) > settings.max_upload_bytes:
        raise PortalError(f"the file exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit")
    busy = db.scalar(
        select(IngestionTaskRecord.id).where(
            IngestionTaskRecord.user_id == user.id,
            IngestionTaskRecord.status.in_([TaskStatus.QUEUED, TaskStatus.PROCESSING]),
        )
    )
    if busy is not None:
        raise PortalError("your previous CV is still being read; try again in a minute")
    task = IngestionTaskRecord(
        status=TaskStatus.QUEUED,
        filename=filename,
        content=data,
        user_id=user.id,
        job_id=job.id if job else None,
        talent_pool_consent=talent_pool_consent,
        attempts=0,
    )
    db.add(task)
    db.commit()
    return task


def apply(
    db: Session,
    settings: Settings,
    user: UserRecord,
    job: JobRecord,
    *,
    data: bytes | None,
    filename: str | None,
    talent_pool_consent: bool | None,
) -> ApplicationRecord | IngestionTaskRecord:
    """Apply to a public job: with a new CV (read in the background), or with the profile already on file."""
    candidate = candidate_of(db, user)
    if candidate is not None and _application(db, candidate, job) is not None:
        raise PortalError("you have already applied to this job")
    if data:
        return queue_cv(
            db, settings, user, data=data, filename=filename, job=job, talent_pool_consent=talent_pool_consent
        )
    if candidate is None:
        raise PortalError("attach your CV to apply")
    return create_portal_application(db, user, candidate, job)


def _application(db: Session, candidate: CandidateRecord, job: JobRecord) -> ApplicationRecord | None:
    return db.scalar(
        select(ApplicationRecord).where(
            ApplicationRecord.candidate_id == candidate.id, ApplicationRecord.job_id == job.id
        )
    )


def create_portal_application(
    db: Session, user: UserRecord, candidate: CandidateRecord, job: JobRecord
) -> ApplicationRecord:
    # The entry belongs to the hiring company's log: they see that the candidate applied.
    set_audit_scope(db, job.organization_id)
    try:
        application = add_to_pipeline(db, candidate, job, actor=user.actor)
    except AlreadyInPipeline as exc:
        raise PortalError("you have already applied to this job") from exc
    application.source = "portal"
    db.commit()
    return application


def applications_of(db: Session, user: UserRecord) -> list[ApplicationRecord]:
    candidate = candidate_of(db, user)
    if candidate is None:
        return []
    return list(
        db.scalars(
            select(ApplicationRecord)
            .where(ApplicationRecord.candidate_id == candidate.id)
            .order_by(ApplicationRecord.created_at.desc())
        )
    )


def own_application(db: Session, user: UserRecord, application_id: uuid.UUID) -> ApplicationRecord | None:
    return db.scalar(
        select(ApplicationRecord)
        .join(CandidateRecord, CandidateRecord.id == ApplicationRecord.candidate_id)
        .where(ApplicationRecord.id == application_id, CandidateRecord.user_id == user.id)
    )


def withdraw(db: Session, user: UserRecord, application: ApplicationRecord) -> ApplicationRecord:
    if application.stage in FINAL_STAGES:
        raise PortalError("this application is already closed")
    set_audit_scope(db, application.job.organization_id)
    return move_application(
        db, application, ApplicationStage.WITHDRAWN, actor=user.actor, reason="withdrawn by the candidate"
    )


def _evidenced_items(value: Any) -> list[Evidenced]:
    if isinstance(value, Evidenced):
        nested = [item for name in type(value).model_fields for item in _evidenced_items(getattr(value, name))]
        return [value, *nested]
    if isinstance(value, list):
        return [item for element in value for item in _evidenced_items(element)]
    if isinstance(value, BaseModel):
        return [item for name in type(value).model_fields for item in _evidenced_items(getattr(value, name))]
    return []


def guard_self_edit(original: CandidateProfile, edited: CandidateProfile) -> CandidateProfile:
    """A candidate may correct or remove what was read from their CV, never raise their own score.

    Every item they add or change is marked unverified (it earns no matching credit), and the stated total years of
    experience keeps the value read from the CV.
    """
    known = {item.model_dump_json() for item in _evidenced_items(original)}
    for item in _evidenced_items(edited):
        if item.model_dump_json() not in known:
            item.verified = False
    edited.total_years_experience = original.total_years_experience
    return edited


def correct_own_profile(
    db: Session, user: UserRecord, candidate: CandidateRecord, profile: CandidateProfile
) -> list[str]:
    guarded = guard_self_edit(CandidateProfile.model_validate(candidate.profile), profile)
    return correct_candidate_profile(db, candidate, guarded, actor=user.actor)
