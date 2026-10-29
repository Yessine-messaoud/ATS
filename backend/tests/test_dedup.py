from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_llm
from app.db import ApplicationRecord, AuditLogRecord, CandidateRecord, JobRecord, MatchRecord, get_session
from app.main import app
from app.search.index import index_candidate
from app.services.dedup import find_duplicates, merge_candidates
from tests.conftest import FakeLLM, make_pdf
from tests.test_extraction import VALID_CV
from tests.test_matching import CANDIDATE


def add(db: Session, **identity: Any) -> CandidateRecord:
    profile = {**CANDIDATE, "identity": identity}
    record = CandidateRecord(profile=profile, schema_version="2", email=identity.get("email"))
    db.add(record)
    db.flush()
    index_candidate(db, record)
    return record


def test_same_email_and_phone_are_detected(db: Session) -> None:
    original = add(db, full_name="Samira Ben Ali", email="Samira@Example.com", phone="+216 20 123 456")
    by_email = add(db, full_name="S. Ben Ali", email="samira@example.com")
    by_phone = add(db, full_name="Someone", phone="20123456")

    found = {d.candidate_id: d.reasons for d in find_duplicates(db, original)}

    assert found[by_email.id] == ["same email"]
    assert "same phone number" in found[by_phone.id]


def test_same_name_needs_a_matching_profile(db: Session) -> None:
    original = add(db, full_name="Mohamed Trabelsi")
    same_person = add(db, full_name="Trabelsi Mohamed")
    namesake = CandidateRecord(
        profile={
            "identity": {"full_name": "Mohamed Trabelsi"},
            "professional_title": "Chef",
            "skills": [{"name": "Pastry"}],
        },
        schema_version="2",
    )
    db.add(namesake)
    db.flush()
    index_candidate(db, namesake)

    found = {d.candidate_id for d in find_duplicates(db, original)}

    assert same_person.id in found
    assert namesake.id not in found  # a common name alone is not evidence


def test_merge_moves_history_and_resolves_pipeline_conflicts(db: Session) -> None:
    keep, duplicate = add(db, full_name="A", email="a@example.com"), add(db, full_name="A", email="a@example.com")
    shared, other = (JobRecord(title=t, profile={"title": t}, schema_version="2") for t in ("Shared", "Other"))
    db.add_all([shared, other])
    db.flush()
    db.add_all(
        [
            ApplicationRecord(candidate_id=keep.id, job_id=shared.id),
            ApplicationRecord(candidate_id=duplicate.id, job_id=shared.id),
            ApplicationRecord(candidate_id=duplicate.id, job_id=other.id),
            MatchRecord(
                candidate_id=duplicate.id,
                job_id=other.id,
                overall_score=50,
                passed_knockouts=True,
                factors={},
                engine_version="x",
            ),
        ]
    )
    db.flush()

    merge_candidates(db, keep, duplicate, actor="recruiter")

    assert db.get(CandidateRecord, duplicate.id) is None
    jobs = sorted(
        db.scalars(select(JobRecord.title).join(ApplicationRecord).where(ApplicationRecord.candidate_id == keep.id))
    )
    assert jobs == ["Other", "Shared"]
    assert db.scalars(select(MatchRecord.candidate_id)).one() == keep.id
    audit = db.scalars(select(AuditLogRecord).where(AuditLogRecord.action == "candidate.merged")).one()
    assert audit.details["applications_moved"] == 1 and audit.details["applications_dropped"] == 1


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_upload_flags_duplicates_and_api_merges_them(client: TestClient) -> None:
    llm = FakeLLM([VALID_CV, VALID_CV])
    app.dependency_overrides[get_llm] = lambda: llm
    first = client.post(
        "/api/candidates/upload",
        files={"file": ("a.pdf", make_pdf(["Samira Ben Ali", "CV v1 text here"]), "application/pdf")},
    ).json()
    second = client.post(
        "/api/candidates/upload",
        files={"file": ("b.pdf", make_pdf(["Samira Ben Ali", "CV v2, updated"]), "application/pdf")},
    ).json()

    assert second["extraction"]["possible_duplicates"][0]["candidate_id"] == first["id"]
    duplicates = client.get(f"/api/candidates/{first['id']}/duplicates").json()
    assert [d["candidate_id"] for d in duplicates] == [second["id"]]

    merged = client.post(f"/api/candidates/{first['id']}/merge", json={"duplicate_id": second["id"]})

    assert merged.status_code == 200, merged.text
    assert client.get(f"/api/candidates/{second['id']}").status_code == 404
    assert client.post(f"/api/candidates/{first['id']}/merge", json={"duplicate_id": first["id"]}).status_code == 409
