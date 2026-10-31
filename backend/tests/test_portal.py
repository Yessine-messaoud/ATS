"""Candidate portal: apply with a CV read in the background, follow the application, own the profile and data."""

from __future__ import annotations

import copy
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.db import (
    ApplicationRecord,
    ApplicationStage,
    CandidateRecord,
    IngestionTaskRecord,
    JobRecord,
    OrganizationRecord,
    OrganizationStatus,
    Role,
    TaskStatus,
    UserRecord,
    get_session,
)
from app.main import app
from app.models import CandidateProfile
from app.services.accounts import create_user, throttle
from app.services.portal import guard_self_edit
from app.services.tasks import claim_next, process
from tests.conftest import FakeLLM, make_pdf
from tests.test_extraction import VALID_CV

PASSWORD = "correct horse battery"
JOB_PROFILE = {"title": "Data Engineer", "skill_requirements": [{"name": "Python", "requirement": "required"}]}


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides.pop(get_current_user, None)
    throttle._failures.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def setting(db: Session) -> dict[str, Any]:
    """An approved company with an open job, its recruiter, and a signed-in candidate."""
    acme = OrganizationRecord(name="Acme", status=OrganizationStatus.ACTIVE, city="Tunis")
    db.add(acme)
    db.flush()
    job = JobRecord(title="Data Engineer", profile=JOB_PROFILE, schema_version="2", organization_id=acme.id)
    db.add(job)
    create_user(db, email="rh@acme.test", password=PASSWORD, full_name="Rania", role=Role.RECRUITER, organization=acme)
    candidate = create_user(db, email="samira@example.com", password=PASSWORD, full_name="Samira", role=Role.CANDIDATE)
    db.flush()
    return {"job": job, "acme": acme, "candidate": candidate}


def sign_in(client: TestClient, email: str) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def apply_with_cv(client: TestClient, headers: dict[str, str], job: JobRecord, **form: Any) -> dict[str, Any]:
    pdf = make_pdf(["Samira Ben Ali", "North Africa Finance - Data Engineer (mars 2022 - présent)", "Python"])
    response = client.post(
        "/api/portal/applications",
        headers=headers,
        data={"job_id": str(job.id), **form},
        files={"file": ("cv.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 202, response.text
    body: dict[str, Any] = response.json()
    return body


def run_worker(db: Session, profile: dict[str, Any] = VALID_CV) -> IngestionTaskRecord:
    task = claim_next(db)
    assert task is not None
    process(db, FakeLLM([profile]), get_settings(), task)
    return task


def test_public_careers_page_lists_open_jobs_of_approved_companies(client: TestClient, setting: dict[str, Any]) -> None:
    jobs = client.get("/api/public/jobs").json()
    assert [j["title"] for j in jobs] == ["Data Engineer"]
    assert jobs[0]["company"]["name"] == "Acme" and jobs[0]["required_skills"] == ["Python"]
    assert client.get("/api/public/jobs?q=python").json() and not client.get("/api/public/jobs?q=cobol").json()
    detail = client.get(f"/api/public/jobs/{setting['job'].id}").json()
    assert detail["company"]["city"] == "Tunis"


def test_apply_reads_the_cv_in_the_background(client: TestClient, db: Session, setting: dict[str, Any]) -> None:
    headers = sign_in(client, "samira@example.com")
    queued = apply_with_cv(client, headers, setting["job"], talent_pool_consent="true")
    assert queued["task"]["status"] == "queued" and queued["application"] is None
    assert client.get("/api/portal/applications", headers=headers).json() == []

    task = run_worker(db)

    assert task.status is TaskStatus.DONE and task.content is None  # the CV bytes do not stay in the queue
    candidate = db.scalars(select(CandidateRecord).where(CandidateRecord.user_id == setting["candidate"].id)).one()
    assert candidate.organization_id is None and candidate.talent_pool_consent is True
    [application] = client.get("/api/portal/applications", headers=headers).json()
    assert application["status"] == "received" and application["status_label"] == "Received"
    assert "score" not in str(application) and application["job"]["company"]["name"] == "Acme"

    recruiter = sign_in(client, "rh@acme.test")
    [pipeline] = client.get(f"/api/jobs/{setting['job'].id}/applications", headers=recruiter).json()
    assert pipeline["source"] == "portal" and pipeline["display_name"] == "Samira Ben Ali"


def test_candidates_follow_decisions_and_can_withdraw(client: TestClient, db: Session, setting: dict[str, Any]) -> None:
    headers = sign_in(client, "samira@example.com")
    apply_with_cv(client, headers, setting["job"])
    run_worker(db)
    application = db.scalars(select(ApplicationRecord)).one()

    recruiter = sign_in(client, "rh@acme.test")
    client.patch(f"/api/applications/{application.id}", headers=recruiter, json={"stage": "interview"})
    [seen] = client.get("/api/portal/applications", headers=headers).json()
    assert seen["status"] == "interview" and seen["can_withdraw"]

    withdrawn = client.post(f"/api/portal/applications/{application.id}/withdraw", headers=headers)
    assert withdrawn.json()["status"] == "withdrawn" and not withdrawn.json()["can_withdraw"]
    assert client.post(f"/api/portal/applications/{application.id}/withdraw", headers=headers).status_code == 422
    db.refresh(application)
    assert application.stage is ApplicationStage.WITHDRAWN


def test_second_application_reuses_the_profile(client: TestClient, db: Session, setting: dict[str, Any]) -> None:
    headers = sign_in(client, "samira@example.com")
    apply_with_cv(client, headers, setting["job"])
    run_worker(db)
    other = JobRecord(
        title="Analyst",
        profile={**JOB_PROFILE, "title": "Analyst"},
        schema_version="2",
        organization_id=setting["acme"].id,
    )
    db.add(other)
    db.flush()

    response = client.post("/api/portal/applications", headers=headers, data={"job_id": str(other.id)})
    assert response.status_code == 202 and response.json()["application"]["status"] == "received"
    again = client.post("/api/portal/applications", headers=headers, data={"job_id": str(other.id)})
    assert again.status_code == 422


def test_applying_without_a_profile_needs_a_cv(client: TestClient, setting: dict[str, Any]) -> None:
    headers = sign_in(client, "samira@example.com")
    response = client.post("/api/portal/applications", headers=headers, data={"job_id": str(setting["job"].id)})
    assert response.status_code == 422 and "CV" in response.json()["detail"]


def test_an_unreadable_cv_fails_with_a_message_for_the_candidate(
    client: TestClient, db: Session, setting: dict[str, Any]
) -> None:
    headers = sign_in(client, "samira@example.com")
    client.post(
        "/api/portal/applications",
        headers=headers,
        data={"job_id": str(setting["job"].id)},
        files={"file": ("cv.exe", b"MZ\x90\x00binary", "application/octet-stream")},
    )
    task = claim_next(db)
    assert task is not None
    process(db, FakeLLM([]), get_settings(), task)
    [shown] = client.get("/api/portal/tasks", headers=headers).json()
    assert shown["status"] == "failed" and "PDF" in shown["error"]


def test_candidates_cannot_raise_their_own_score() -> None:
    original = CandidateProfile.model_validate(
        {**VALID_CV, "skills": [{"name": "Python", "verified": True}, {"name": "Spark", "verified": False}]}
    )
    edited = CandidateProfile.model_validate(
        {
            **VALID_CV,
            "total_years_experience": 25,
            "skills": [
                {"name": "Python", "verified": True},  # unchanged: stays verified
                {"name": "Spark", "verified": True},  # self-verified: refused
                {"name": "Kubernetes", "verified": True},  # added: unverified
            ],
        }
    )
    guarded = guard_self_edit(original, copy.deepcopy(edited))
    assert [s.verified for s in guarded.skills] == [True, False, False]
    assert guarded.total_years_experience == original.total_years_experience


def test_candidates_correct_export_and_delete_their_data(
    client: TestClient, db: Session, setting: dict[str, Any]
) -> None:
    headers = sign_in(client, "samira@example.com")
    apply_with_cv(client, headers, setting["job"])
    run_worker(db)

    profile = client.get("/api/portal/profile", headers=headers).json()
    corrected = {**profile["profile"], "professional_title": "Senior Data Engineer"}
    assert (
        client.put("/api/portal/profile", headers=headers, json=corrected).json()["profile"]["professional_title"]
        == "Senior Data Engineer"
    )
    assert (
        client.put("/api/portal/consent", headers=headers, json={"consent": False}).json()["talent_pool_consent"]
        is False
    )

    exported = client.get("/api/portal/export", headers=headers)
    assert exported.json()["account"]["email"] == "samira@example.com" and exported.json()["candidate"]

    assert (
        client.request(
            "DELETE", "/api/portal/account", headers=headers, json={"password": "wrong password"}
        ).status_code
        == 422
    )
    assert (
        client.request("DELETE", "/api/portal/account", headers=headers, json={"password": PASSWORD}).status_code == 204
    )
    assert db.scalars(select(CandidateRecord)).all() == [] and db.scalars(select(ApplicationRecord)).all() == []
    assert db.scalar(select(UserRecord).where(UserRecord.email == "samira@example.com")) is None


def test_a_new_cv_replaces_the_profile_and_keeps_applications(
    client: TestClient, db: Session, setting: dict[str, Any]
) -> None:
    headers = sign_in(client, "samira@example.com")
    apply_with_cv(client, headers, setting["job"])
    run_worker(db)
    pdf = make_pdf(["Samira Ben Ali", "Updated CV", "Python, Spark"])
    assert (
        client.post("/api/portal/cv", headers=headers, files={"file": ("cv2.pdf", pdf, "application/pdf")}).status_code
        == 202
    )
    run_worker(db, {**VALID_CV, "professional_title": "Lead Data Engineer"})

    candidates = db.scalars(select(CandidateRecord)).all()
    assert len(candidates) == 1 and candidates[0].profile["professional_title"] == "Lead Data Engineer"
    assert len(client.get("/api/portal/applications", headers=headers).json()) == 1
    assert client.get("/api/portal/profile", headers=headers).json()["filename"] == "cv2.pdf"
