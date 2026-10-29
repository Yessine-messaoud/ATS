"""Integration tests against the migrated Postgres database (skipped when it is unreachable)."""

from collections.abc import Iterator

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import ApplicationRecord, ApplicationStage, CandidateRecord, JobRecord, get_engine
from app.models import CandidateProfile, JobProfile
from examples.profiles import candidate, job


@pytest.fixture
def session() -> Iterator[Session]:
    try:
        connection = get_engine().connect()
    except OperationalError:
        pytest.skip("Postgres is not reachable; run `docker compose up -d postgres` and `alembic upgrade head`")

    transaction = connection.begin()
    connection.execute(text("SELECT 1 FROM alembic_version"))
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


def test_profiles_round_trip_through_jsonb(session: Session) -> None:
    candidate_record = CandidateRecord(
        profile=candidate.model_dump(mode="json"),
        schema_version=candidate.schema_version,
        email=candidate.identity.email,
    )
    job_record = JobRecord(title=job.title, profile=job.model_dump(mode="json"), schema_version=job.schema_version)
    session.add_all([candidate_record, job_record])
    session.flush()
    session.add(ApplicationRecord(candidate_id=candidate_record.id, job_id=job_record.id))
    session.flush()
    session.expire_all()

    application = session.scalars(select(ApplicationRecord)).one()

    assert application.stage is ApplicationStage.NEW
    assert CandidateProfile.model_validate(application.candidate.profile) == candidate
    assert JobProfile.model_validate(application.job.profile) == job
    assert application.candidate.created_at is not None
