"""Applications and their stages. Every stage change is a logged human decision."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import ApplicationRecord, ApplicationStage, AuditLogRecord, CandidateRecord, JobRecord


class AlreadyInPipeline(Exception):
    def __init__(self, existing_id: uuid.UUID) -> None:
        super().__init__(f"the candidate is already in this job's pipeline (application {existing_id})")
        self.existing_id = existing_id


def add_to_pipeline(db: Session, candidate: CandidateRecord, job: JobRecord, *, actor: str) -> ApplicationRecord:
    existing = db.scalar(
        select(ApplicationRecord.id).where(
            ApplicationRecord.candidate_id == candidate.id, ApplicationRecord.job_id == job.id
        )
    )
    if existing is not None:
        raise AlreadyInPipeline(existing)
    # The (candidate_id, job_id) unique constraint also protects against concurrent inserts.
    application = ApplicationRecord(candidate_id=candidate.id, job_id=job.id, stage=ApplicationStage.NEW)
    db.add(application)
    db.flush()
    db.add(
        AuditLogRecord(
            actor=actor,
            action="application.created",
            entity_type="application",
            entity_id=application.id,
            details={"candidate_id": str(candidate.id), "job_id": str(job.id)},
        )
    )
    db.commit()
    return application


def move_application(
    db: Session, application: ApplicationRecord, stage: ApplicationStage, *, actor: str, reason: str | None
) -> ApplicationRecord:
    previous = application.stage
    if previous is stage:
        return application
    application.stage = stage
    db.add(
        AuditLogRecord(
            actor=actor,
            action="application.stage_changed",
            entity_type="application",
            entity_id=application.id,
            details={"from": previous.value, "to": stage.value, "reason": reason},
        )
    )
    db.commit()
    return application


def job_applications(db: Session, job: JobRecord) -> list[ApplicationRecord]:
    return list(
        db.scalars(
            select(ApplicationRecord).where(ApplicationRecord.job_id == job.id).order_by(ApplicationRecord.created_at)
        )
    )
