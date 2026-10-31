"""Accounts, roles and company isolation, through the API with real sign-in sessions."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import (
    ApplicationRecord,
    AuditLogRecord,
    CandidateRecord,
    JobRecord,
    OrganizationRecord,
    OrganizationStatus,
    Role,
    SessionRecord,
    UserRecord,
    get_session,
)
from app.main import app
from app.security.passwords import hash_password, verify_password
from app.services.accounts import create_user, throttle

PASSWORD = "correct horse battery"
JOB_PROFILE = {"title": "Data Engineer", "skill_requirements": [{"name": "Python", "requirement": "required"}]}
CANDIDATE_PROFILE = {"identity": {"full_name": "Samira Ben Ali"}, "skills": [{"name": "Python"}]}


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides.pop(get_current_user, None)  # real sessions in this module
    throttle._failures.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


def company(db: Session, name: str, status: OrganizationStatus = OrganizationStatus.ACTIVE) -> OrganizationRecord:
    organization = OrganizationRecord(name=name, status=status)
    db.add(organization)
    db.flush()
    return organization


def user(db: Session, email: str, role: Role, organization: OrganizationRecord | None = None) -> UserRecord:
    return create_user(
        db, email=email, password=PASSWORD, full_name=email.split("@")[0], role=role, organization=organization
    )


def sign_in(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def job_of(db: Session, organization: OrganizationRecord, title: str = "Data Engineer") -> JobRecord:
    job = JobRecord(
        title=title, profile={**JOB_PROFILE, "title": title}, schema_version="2", organization_id=organization.id
    )
    db.add(job)
    db.flush()
    return job


def candidate_of(db: Session, organization: OrganizationRecord | None, **fields: Any) -> CandidateRecord:
    candidate = CandidateRecord(
        profile=CANDIDATE_PROFILE,
        schema_version="2",
        organization_id=organization.id if organization else None,
        **fields,
    )
    db.add(candidate)
    db.flush()
    return candidate


# --- passwords and sessions ---------------------------------------------------------------------------------------


def test_password_hashes_are_salted_and_verified() -> None:
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first != second and first.startswith("scrypt$")
    assert verify_password(PASSWORD, first) and not verify_password("wrong password!", first)
    assert not verify_password(PASSWORD, "not-a-hash")


def test_register_sign_in_and_out(client: TestClient, db: Session) -> None:
    response = client.post(
        "/api/auth/register",
        json={"account_type": "candidate", "email": "Lina@Example.com", "password": PASSWORD, "full_name": "Lina"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["email"] == "lina@example.com" and body["user"]["role"] == "candidate"
    stored = db.scalars(select(SessionRecord)).one()
    assert stored.token_hash != body["token"]  # only the hash is stored

    headers = {"Authorization": f"Bearer {body['token']}"}
    assert client.get("/api/auth/me", headers=headers).json()["full_name"] == "Lina"
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_bad_credentials_weak_passwords_and_throttling(client: TestClient, db: Session) -> None:
    user(db, "nour@example.com", Role.CANDIDATE)
    weak = client.post(
        "/api/auth/register",
        json={"account_type": "candidate", "email": "x@example.com", "password": "short", "full_name": "X"},
    )
    assert weak.status_code == 422
    for _ in range(5):
        assert (
            client.post("/api/auth/login", json={"email": "nour@example.com", "password": "wrong password"}).status_code
            == 401
        )
    # Even the right password is refused once throttled.
    assert client.post("/api/auth/login", json={"email": "nour@example.com", "password": PASSWORD}).status_code == 429


def test_password_change_signs_out_other_sessions(client: TestClient, db: Session) -> None:
    user(db, "omar@example.com", Role.CANDIDATE)
    first, second = sign_in(client, "omar@example.com"), sign_in(client, "omar@example.com")
    response = client.post(
        "/api/auth/password", headers=first, json={"current_password": PASSWORD, "new_password": "a brand new secret"}
    )
    assert response.status_code == 200, response.text
    assert client.get("/api/auth/me", headers=second).status_code == 401
    assert (
        client.get("/api/auth/me", headers={"Authorization": f"Bearer {response.json()['token']}"}).status_code == 200
    )


# --- roles ------------------------------------------------------------------------------------------------------------


def test_routes_require_the_right_role(client: TestClient, db: Session) -> None:
    acme = company(db, "Acme")
    user(db, "rh@acme.test", Role.RECRUITER, acme)
    user(db, "cand@example.com", Role.CANDIDATE)
    recruiter, candidate = sign_in(client, "rh@acme.test"), sign_in(client, "cand@example.com")

    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/jobs", headers=candidate).status_code == 403
    assert client.get("/api/jobs", headers=recruiter).status_code == 200
    assert client.get("/api/admin/overview", headers=recruiter).status_code == 403
    assert client.get("/api/portal/applications", headers=recruiter).status_code == 403
    assert client.get("/api/public/jobs").status_code == 200  # the careers page is public


# --- company isolation ------------------------------------------------------------------------------------------------


def test_companies_only_see_their_own_data(client: TestClient, db: Session) -> None:
    acme, globex = company(db, "Acme"), company(db, "Globex")
    user(db, "rh@acme.test", Role.RECRUITER, acme)
    acme_job, globex_job = job_of(db, acme), job_of(db, globex)
    acme_cv, globex_cv = candidate_of(db, acme), candidate_of(db, globex)
    headers = sign_in(client, "rh@acme.test")

    assert [j["id"] for j in client.get("/api/jobs", headers=headers).json()] == [str(acme_job.id)]
    assert [c["id"] for c in client.get("/api/candidates", headers=headers).json()] == [str(acme_cv.id)]
    # Other companies' records are "not found", not "forbidden".
    assert client.get(f"/api/jobs/{globex_job.id}", headers=headers).status_code == 404
    assert client.get(f"/api/candidates/{globex_cv.id}", headers=headers).status_code == 404
    ranking = client.get(f"/api/jobs/{acme_job.id}/ranking", headers=headers).json()
    assert {r["candidate_id"] for r in ranking["ranked"] + ranking["knocked_out"]} == {str(acme_cv.id)}
    added = client.post(
        "/api/applications", headers=headers, json={"candidate_id": str(globex_cv.id), "job_id": str(acme_job.id)}
    )
    assert added.status_code == 404


def test_audit_log_is_per_company(client: TestClient, db: Session) -> None:
    acme, globex = company(db, "Acme"), company(db, "Globex")
    user(db, "rh@acme.test", Role.RECRUITER, acme)
    user(db, "rh@globex.test", Role.RECRUITER, globex)
    acme_headers, globex_headers = sign_in(client, "rh@acme.test"), sign_in(client, "rh@globex.test")
    job = job_of(db, acme)
    client.put(f"/api/jobs/{job.id}/weights", headers=acme_headers, json={"skills": 2})

    entry = db.scalars(select(AuditLogRecord).where(AuditLogRecord.action == "job.weights_updated")).one()
    assert entry.organization_id == acme.id and entry.actor.startswith("user:")
    acme_log = client.get("/api/audit?action=job.weights_updated", headers=acme_headers).json()
    assert [e["actor_name"] for e in acme_log] == ["rh"]
    assert client.get("/api/audit?action=job.weights_updated", headers=globex_headers).json() == []


def test_portal_candidates_are_visible_to_the_companies_they_applied_to(client: TestClient, db: Session) -> None:
    acme, globex = company(db, "Acme"), company(db, "Globex")
    user(db, "rh@acme.test", Role.RECRUITER, acme)
    owner = user(db, "lina@example.com", Role.CANDIDATE)
    job = job_of(db, globex)
    portal = candidate_of(db, None, user_id=owner.id)
    headers = sign_in(client, "rh@acme.test")

    assert client.get(f"/api/candidates/{portal.id}", headers=headers).status_code == 404
    db.add(ApplicationRecord(candidate_id=portal.id, job_id=job_of(db, acme, "Analyst").id, source="portal"))
    db.flush()
    seen = client.get(f"/api/candidates/{portal.id}", headers=headers)
    assert seen.status_code == 200 and seen.json()["source"] == "portal"
    # The company can read and decide, not rewrite the candidate's own profile or erase them.
    assert client.delete(f"/api/candidates/{portal.id}", headers=headers).status_code == 403
    assert job.organization_id == globex.id


def test_talent_pool_consent_opens_a_portal_profile_to_every_company(client: TestClient, db: Session) -> None:
    acme = company(db, "Acme")
    user(db, "rh@acme.test", Role.RECRUITER, acme)
    owner = user(db, "lina@example.com", Role.CANDIDATE)
    portal = candidate_of(db, None, user_id=owner.id, talent_pool_consent=True)
    assert client.get(f"/api/candidates/{portal.id}", headers=sign_in(client, "rh@acme.test")).status_code == 200


# --- admin --------------------------------------------------------------------------------------------------------


def test_admin_approves_and_suspends_companies(client: TestClient, db: Session) -> None:
    user(db, "admin@platform.test", Role.ADMIN)
    admin = sign_in(client, "admin@platform.test")
    registered = client.post(
        "/api/auth/register",
        json={
            "account_type": "company",
            "company_name": "Initech",
            "email": "rh@initech.test",
            "password": PASSWORD,
            "full_name": "Bill",
        },
    ).json()
    organization = registered["user"]["organization"]
    assert organization["status"] == "pending"
    db.add(
        JobRecord(
            title="Engineer",
            profile={**JOB_PROFILE, "title": "Engineer"},
            schema_version="2",
            organization_id=uuid.UUID(organization["id"]),
        )
    )
    db.flush()
    assert client.get("/api/public/jobs").json() == []  # pending companies are not on the careers page

    approved = client.patch(f"/api/admin/organizations/{organization['id']}", headers=admin, json={"status": "active"})
    assert approved.status_code == 200 and approved.json()["jobs"] == 1
    assert [j["title"] for j in client.get("/api/public/jobs").json()] == ["Engineer"]

    recruiter = {"Authorization": f"Bearer {registered['token']}"}
    client.patch(f"/api/admin/organizations/{organization['id']}", headers=admin, json={"status": "suspended"})
    assert client.get("/api/jobs", headers=recruiter).status_code == 401  # signed out
    assert client.post("/api/auth/login", json={"email": "rh@initech.test", "password": PASSWORD}).status_code == 401
    assert client.get("/api/public/jobs").json() == []


def test_admin_creates_staff_with_a_one_time_password(client: TestClient, db: Session) -> None:
    acme = company(db, "Acme")
    user(db, "admin@platform.test", Role.ADMIN)
    admin = sign_in(client, "admin@platform.test")
    created = client.post(
        "/api/admin/users",
        headers=admin,
        json={"email": "new@acme.test", "full_name": "New", "role": "recruiter", "organization_id": str(acme.id)},
    )
    assert created.status_code == 201, created.text
    assert (
        client.post(
            "/api/auth/login", json={"email": "new@acme.test", "password": created.json()["temporary_password"]}
        ).status_code
        == 200
    )
    overview = client.get("/api/admin/overview", headers=admin).json()
    assert overview["users"]["recruiter"] == 1 and overview["organizations"]["active"] >= 1
    assert (
        client.patch(
            f"/api/admin/users/{created.json()['user']['id']}", headers=admin, json={"is_active": False}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/login", json={"email": "new@acme.test", "password": created.json()["temporary_password"]}
        ).status_code
        == 401
    )


def test_recruiters_manage_their_company_and_team(client: TestClient, db: Session) -> None:
    acme = company(db, "Acme")
    user(db, "rh@acme.test", Role.RECRUITER, acme)
    headers = sign_in(client, "rh@acme.test")
    updated = client.put(
        "/api/organization", headers=headers, json={"name": "Acme Corp", "city": "Sfax", "website": ""}
    )
    assert updated.json()["name"] == "Acme Corp" and updated.json()["website"] is None
    member = client.post(
        "/api/organization/members", headers=headers, json={"email": "two@acme.test", "full_name": "Two"}
    )
    assert member.status_code == 201
    assert {m["email"] for m in client.get("/api/organization/members", headers=headers).json()} == {
        "rh@acme.test",
        "two@acme.test",
    }
