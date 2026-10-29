"""Integration tests against the migrated test database (skipped when Postgres is unreachable)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import ApplicationRecord, ApplicationStage, CandidateRecord, JobRecord
from app.models import CandidateProfile, JobProfile
from examples.profiles import candidate, job


def test_profiles_round_trip_through_jsonb(db: Session) -> None:
    candidate_record = CandidateRecord(
        profile=candidate.model_dump(mode="json"),
        schema_version=candidate.schema_version,
        email=candidate.identity.email,
    )
    job_record = JobRecord(title=job.title, profile=job.model_dump(mode="json"), schema_version=job.schema_version)
    db.add_all([candidate_record, job_record])
    db.flush()
    db.add(ApplicationRecord(candidate_id=candidate_record.id, job_id=job_record.id))
    db.flush()
    db.expire_all()

    application = db.scalars(select(ApplicationRecord)).one()

    assert application.stage is ApplicationStage.NEW
    assert CandidateProfile.model_validate(application.candidate.profile) == candidate
    assert JobProfile.model_validate(application.job.profile) == job
    assert application.candidate.created_at is not None
