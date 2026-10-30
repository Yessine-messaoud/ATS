from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.api.deps import get_llm
from app.config import Settings, get_settings
from app.db import (
    AgentConversationRecord,
    ApplicationRecord,
    AuditLogRecord,
    CandidateRecord,
    CandidateSearchRecord,
    DocumentRecord,
    JobRecord,
    MatchRecord,
    get_session,
)
from app.main import app
from app.security import crypto
from app.security.crypto import PREFIX, DecryptionError, DocumentCipher, generate_key
from app.security.logs import PiiFilter, redact
from app.services.matching import rank_candidates, recommend_jobs
from app.services.privacy import run_retention
from scripts.encrypt_documents import run as encrypt_documents
from tests.conftest import FakeLLM, make_pdf
from tests.test_extraction import VALID_CV

JOB_PROFILE = {"title": "Data Engineer", "skill_requirements": [{"name": "Python", "requirement": "required"}]}


@pytest.fixture
def key(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    value = generate_key()
    monkeypatch.setenv("DOCUMENT_ENCRYPTION_KEYS", value)
    get_settings.cache_clear()
    crypto.get_cipher.cache_clear()
    yield value
    monkeypatch.delenv("DOCUMENT_ENCRYPTION_KEYS")
    get_settings.cache_clear()
    crypto.get_cipher.cache_clear()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def upload(client: TestClient, profile: dict[str, Any] = VALID_CV, line: str = "") -> dict[str, Any]:
    app.dependency_overrides[get_llm] = lambda: FakeLLM([profile])
    pdf = make_pdf(["Samira Ben Ali", "North Africa Finance - Data Engineer (mars 2022 - présent)", line])
    response = client.post("/api/candidates/upload", files={"file": ("cv.pdf", pdf, "application/pdf")})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def stored_bytes(db: Session, column: str) -> bytes:
    return bytes(db.execute(text(f"SELECT {column} FROM documents LIMIT 1")).scalar_one())


def add_job(db: Session, status: str = "open") -> JobRecord:
    job = JobRecord(title="Data Engineer", profile=JOB_PROFILE, schema_version="2", status=status)
    db.add(job)
    db.flush()
    return job


# --- encryption at rest -------------------------------------------------------------------------------------------


def test_cipher_round_trip_and_rotation() -> None:
    old, new = generate_key(), generate_key()
    token = DocumentCipher([old]).encrypt(b"cv")
    assert token.startswith(PREFIX) and b"cv" not in token
    assert DocumentCipher([new, old]).decrypt(token) == b"cv"
    rotated = DocumentCipher([new, old]).rotate(token)
    assert DocumentCipher([new]).decrypt(rotated) == b"cv"
    with pytest.raises(DecryptionError):
        DocumentCipher([new]).decrypt(token)
    with pytest.raises(DecryptionError):
        DocumentCipher([]).decrypt(token)
    assert DocumentCipher([]).decrypt(b"legacy plaintext") == b"legacy plaintext"


def test_documents_are_encrypted_in_the_database(client: TestClient, db: Session, key: str) -> None:
    candidate = upload(client)

    assert stored_bytes(db, "content").startswith(PREFIX)
    assert stored_bytes(db, "raw_text").startswith(PREFIX)
    assert b"North Africa" not in stored_bytes(db, "raw_text")
    db.expire_all()
    assert "North Africa Finance" in client.get(f"/api/candidates/{candidate['id']}/document").json()["raw_text"]
    assert client.get(f"/api/candidates/{candidate['id']}/document/file").content.startswith(b"%PDF")


def test_plaintext_rows_are_encrypted_by_the_script(client: TestClient, db: Session, monkeypatch: Any) -> None:
    upload(client)  # no key configured: stored in plaintext
    assert not stored_bytes(db, "raw_text").startswith(PREFIX)

    monkeypatch.setenv("DOCUMENT_ENCRYPTION_KEYS", generate_key())
    get_settings.cache_clear()
    crypto.get_cipher.cache_clear()
    try:
        assert encrypt_documents(db) == 1
        assert stored_bytes(db, "raw_text").startswith(PREFIX)
        assert encrypt_documents(db) == 0  # idempotent
        db.expire_all()
        assert "North Africa" in (db.scalars(select(DocumentRecord)).one().raw_text or "")
        assert encrypt_documents(db, decrypt=True) == 1
        assert not stored_bytes(db, "raw_text").startswith(PREFIX)
    finally:
        monkeypatch.delenv("DOCUMENT_ENCRYPTION_KEYS")
        get_settings.cache_clear()
        crypto.get_cipher.cache_clear()


def test_production_requires_an_encryption_key() -> None:
    assert Settings(document_encryption_keys=None).production_problems()
    assert Settings(document_encryption_keys=generate_key(), debug=False).production_problems() == []


# --- logs -----------------------------------------------------------------------------------------------------------


def test_logs_are_redacted() -> None:
    assert redact("upload from samira.benali@example.com, tel +216 20 000 000") == "upload from [email], tel [phone]"
    assert redact("candidate 3f2a, 12 skills, year 2024, 200 OK") == "candidate 3f2a, 12 skills, year 2024, 200 OK"

    import logging

    record = logging.LogRecord("app", logging.INFO, __file__, 1, "contact %s", ("jane@example.org",), None)
    PiiFilter().filter(record)
    assert record.getMessage() == "contact [email]"


# --- export and erasure ---------------------------------------------------------------------------------------------


def test_export_contains_everything_held(client: TestClient, db: Session) -> None:
    candidate = upload(client)
    job = add_job(db)
    client.post("/api/applications", json={"candidate_id": candidate["id"], "job_id": str(job.id)})
    client.post(f"/api/matches?candidate_id={candidate['id']}&job_id={job.id}")

    response = client.get(f"/api/candidates/{candidate['id']}/export")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    data = response.json()
    assert data["format"] == "ats-candidate-export-v1"
    assert data["candidate"]["profile"]["identity"]["full_name"] == "Samira Ben Ali"
    assert "North Africa Finance" in data["documents"][0]["extracted_text"]
    assert [a["job_title"] for a in data["applications"]] == ["Data Engineer"]
    assert {e["action"] for e in data["processing_log"]} >= {"candidate.extracted", "application.created"}
    assert db.scalars(select(AuditLogRecord.action).where(AuditLogRecord.action == "candidate.exported")).one()


def test_erasure_removes_all_personal_data(client: TestClient, db: Session) -> None:
    candidate = upload(client)
    other = upload(client, {**VALID_CV, "identity": {"full_name": "Other Person"}}, line="Different file")
    job = add_job(db)
    application = client.post("/api/applications", json={"candidate_id": candidate["id"], "job_id": str(job.id)})
    client.patch(
        f"/api/applications/{application.json()['id']}", json={"stage": "rejected", "reason": "Samira said no"}
    )
    db.add(
        MatchRecord(
            candidate_id=candidate["id"],
            job_id=job.id,
            overall_score=50,
            passed_knockouts=True,
            factors={},
            engine_version="t",
        )
    )
    db.add(
        AgentConversationRecord(messages=[{"role": "user", "content": f"Tell me about {candidate['id']}"}], usage={})
    )
    db.add(AgentConversationRecord(messages=[{"role": "user", "content": "unrelated"}], usage={}))
    db.flush()

    response = client.delete(f"/api/candidates/{candidate['id']}?reason=candidate%20request%20by%20email")

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["documents"] == 1 and report["applications"] == 1 and report["matches"] == 1
    assert report["conversations"] == 1 and report["audit_entries_redacted"] == 1
    db.expire_all()
    assert client.get(f"/api/candidates/{candidate['id']}").status_code == 404
    assert db.get(CandidateRecord, other["id"]) is not None
    assert db.scalars(select(DocumentRecord)).all() != [] and len(db.scalars(select(DocumentRecord)).all()) == 1
    assert db.scalars(select(ApplicationRecord)).all() == []
    assert db.scalars(select(MatchRecord)).all() == []
    assert db.get(CandidateSearchRecord, candidate["id"]) is None
    assert len(db.scalars(select(AgentConversationRecord)).all()) == 1
    log = " ".join(str(e.details) for e in db.scalars(select(AuditLogRecord)))
    assert "Samira said no" not in log
    erased = db.scalars(select(AuditLogRecord).where(AuditLogRecord.action == "candidate.erased")).one()
    assert erased.details["reason"] == "candidate request by email"


# --- consent ----------------------------------------------------------------------------------------------------------


def test_consent_limits_the_pool_when_required(client: TestClient, db: Session) -> None:
    consenting = upload(client)
    silent = upload(client, {**VALID_CV, "identity": {"full_name": "Silent"}}, line="Another CV")
    applicant = upload(client, {**VALID_CV, "identity": {"full_name": "Applicant"}}, line="Third CV")
    job = add_job(db)
    response = client.put(f"/api/candidates/{consenting['id']}/consent", json={"consent": True})
    assert response.json()["talent_pool_consent"] is True
    client.post("/api/applications", json={"candidate_id": applicant["id"], "job_id": str(job.id)})

    def pool(required: bool) -> set[str]:
        run = rank_candidates(db, job, limit=50, full_scoring_limit=500, retrieval_k=200, consent_required=required)
        return {str(r.candidate.id) for r in [*run.passed, *run.knocked_out]}

    assert pool(False) == {consenting["id"], silent["id"], applicant["id"]}
    assert pool(True) == {consenting["id"], applicant["id"]}
    other_job = add_job(db)
    silent_record = db.get_one(CandidateRecord, silent["id"])
    assert recommend_jobs(db, silent_record, limit=10, consent_required=True) == []
    assert {r.job.id for r in recommend_jobs(db, silent_record, limit=10)} == {job.id, other_job.id}
    actions = db.scalars(select(AuditLogRecord.details).where(AuditLogRecord.action == "candidate.consent_updated"))
    assert actions.all() == [{"from": None, "to": True}]


# --- retention ------------------------------------------------------------------------------------------------------


def test_retention_purges_documents_and_erases_inactive_candidates(client: TestClient, db: Session) -> None:
    kept = upload(client)
    inactive = upload(client, {**VALID_CV, "identity": {"full_name": "Inactive"}}, line="Old CV")
    consented = upload(client, {**VALID_CV, "identity": {"full_name": "Consented"}}, line="Pool CV")
    client.put(f"/api/candidates/{consented['id']}/consent", json={"consent": True})
    settings = Settings()
    now = datetime.now(UTC) + timedelta(days=settings.document_retention_days + 1)
    old = now - timedelta(days=settings.candidate_retention_days + 1)
    db.execute(
        update(CandidateRecord).where(CandidateRecord.id.in_([inactive["id"], consented["id"]])).values(updated_at=old)
    )
    db.flush()

    dry = run_retention(db, settings, now=now, dry_run=True)
    assert dry.documents_purged == 3 and dry.candidates_erased == [inactive["id"]]
    assert db.get(CandidateRecord, inactive["id"]) is not None

    report = run_retention(db, settings, now=now)

    assert report.candidates_erased == [inactive["id"]]
    db.expire_all()
    assert db.get(CandidateRecord, inactive["id"]) is None
    assert db.get(CandidateRecord, consented["id"]) is not None
    document = client.get(f"/api/candidates/{kept['id']}/document").json()
    assert document["raw_text"] is None and document["purged_at"] is not None
    file = client.get(f"/api/candidates/{kept['id']}/document/file")
    assert file.status_code == 404 and "retention" in file.json()["detail"]
    assert run_retention(db, settings, now=now).documents_purged == 0


# --- audit log --------------------------------------------------------------------------------------------------------


def test_audit_log_endpoint_filters(client: TestClient, db: Session) -> None:
    candidate = upload(client)
    client.put(f"/api/candidates/{candidate['id']}/consent", json={"consent": False})

    entries = client.get(f"/api/audit?entity_id={candidate['id']}").json()
    # same transaction, same now(): compare as a set
    assert {e["action"] for e in entries} == {"candidate.consent_updated", "candidate.extracted"}
    assert [e["action"] for e in client.get("/api/audit?action=candidate.consent_updated").json()] == [
        "candidate.consent_updated"
    ]
    assert len(client.get("/api/audit?action=candidate.").json()) == 2
    assert client.get("/api/audit?actor=nobody").json() == []


def test_privacy_policy_reflects_the_configuration(client: TestClient, key: str) -> None:
    policy = client.get("/api/privacy/policy").json()

    assert policy["documents_encrypted"] is True
    assert policy["document_retention_days"] == Settings().document_retention_days
    assert policy["scoring_engine"].startswith("match-v1")
