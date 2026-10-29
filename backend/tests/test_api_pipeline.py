from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import AuditLogRecord, CandidateRecord, JobRecord, get_session
from app.main import app
from scripts.seed_demo import seed


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def demo(db: Session) -> dict[str, int]:
    return seed(db)


def candidate_named(db: Session, name: str) -> CandidateRecord:
    return next(c for c in db.scalars(select(CandidateRecord)) if c.profile["identity"]["full_name"] == name)


def job_titled(db: Session, title: str) -> JobRecord:
    return db.scalars(select(JobRecord).where(JobRecord.title == title)).one()


def test_seed_is_idempotent(db: Session, demo: dict[str, int]) -> None:
    assert demo == {"candidates": 6, "jobs": 3, "applications": 4}
    assert seed(db) == {"candidates": 0, "jobs": 0, "applications": 0}


def test_seeded_adversarial_cv_is_flagged(client: TestClient, db: Session, demo: dict[str, int]) -> None:
    karim = candidate_named(db, "Karim Mansour")

    document = client.get(f"/api/candidates/{karim.id}/document").json()

    assert "hidden_text" in document["flags"]
    assert "possible_prompt_injection" in document["flags"]
    assert document["hidden_text"]
    assert client.get(f"/api/candidates/{karim.id}/document/file").headers["content-type"] == "application/pdf"


def test_pipeline_add_move_and_audit(client: TestClient, db: Session, demo: dict[str, int]) -> None:
    job = job_titled(db, "Data Engineer")
    devops = candidate_named(db, "Mehdi Jlassi")

    created = client.post("/api/applications", json={"candidate_id": str(devops.id), "job_id": str(job.id)})
    duplicate = client.post("/api/applications", json={"candidate_id": str(devops.id), "job_id": str(job.id)})

    assert created.status_code == 201, created.text
    assert duplicate.status_code == 409
    moved = client.patch(f"/api/applications/{created.json()['id']}", json={"stage": "rejected", "reason": "no Spark"})
    assert moved.json()["stage"] == "rejected"
    pipeline = client.get(f"/api/jobs/{job.id}/applications").json()
    assert {a["display_name"]: a["stage"] for a in pipeline}["Mehdi Jlassi"] == "rejected"
    assert all(a["overall_score"] is not None for a in pipeline)
    change = db.scalars(select(AuditLogRecord).where(AuditLogRecord.action == "application.stage_changed")).one()
    assert change.details == {"from": "new", "to": "rejected", "reason": "no Spark"}


def test_blind_pipeline_hides_names(client: TestClient, db: Session, demo: dict[str, int]) -> None:
    job = job_titled(db, "Data Engineer")

    names = [a["display_name"] for a in client.get(f"/api/jobs/{job.id}/applications", params={"blind": True}).json()]

    assert names and all(name.startswith("Candidate ") for name in names)


def test_profile_correction_keeps_original_and_logs_paths_only(
    client: TestClient, db: Session, demo: dict[str, int]
) -> None:
    karim = candidate_named(db, "Karim Mansour")
    profile = client.get(f"/api/candidates/{karim.id}").json()["profile"]
    profile["skills"] = [s for s in profile["skills"] if s["name"] != "Kubernetes"]  # recruiter removes the fake skill
    profile["professional_title"] = "Backend Developer"

    response = client.put(f"/api/candidates/{karim.id}/profile", json=profile)

    assert response.status_code == 200, response.text
    body = response.json()
    assert "professional_title" in body["changed_paths"]
    assert body["candidate"]["profile"]["professional_title"] == "Backend Developer"
    assert any(s["name"] == "Kubernetes" for s in body["candidate"]["extraction"]["extracted_profile"]["skills"])
    audit = db.scalars(select(AuditLogRecord).where(AuditLogRecord.action == "candidate.profile_corrected")).one()
    assert "Backend Developer" not in str(audit.details)  # paths only, never values
    assert (
        client.put(f"/api/candidates/{karim.id}/profile", json=body["candidate"]["profile"]).json()["changed_paths"]
        == []
    )


def test_closed_jobs_are_not_recommended(client: TestClient, db: Session, demo: dict[str, int]) -> None:
    job = job_titled(db, "Data Engineer")
    samira = candidate_named(db, "Samira Ben Ali")

    assert client.patch(f"/api/jobs/{job.id}", json={"status": "closed"}).json()["status"] == "closed"

    titles = [r["title"] for r in client.get(f"/api/candidates/{samira.id}/recommendations").json()]
    assert "Data Engineer" not in titles
    assert client.patch(f"/api/jobs/{job.id}", json={"status": "archived"}).status_code == 422
