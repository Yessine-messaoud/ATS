from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_llm
from app.db import AuditLogRecord, DocumentRecord, get_session
from app.extraction import LLMError
from app.main import app
from tests.conftest import FakeLLM, make_pdf
from tests.test_extraction import VALID_CV

JOB_TEXT = (
    "Data Engineer (CDI) - Tunis, hybrid. Required: Python, SQL, 3+ years of experience. "
    "Nice to have: Spark. English B2 required."
)
VALID_JOB = {
    "title": "Data Engineer",
    "contract_type": "permanent",
    "work_mode": "hybrid",
    "skill_requirements": [
        {"name": "Python", "requirement": "required", "evidence": "Required: Python"},
        {"name": "Spark", "requirement": "preferred", "evidence": "Nice to have: Spark"},
    ],
}


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_llm(*responses: dict[str, Any] | None) -> FakeLLM:
    llm = FakeLLM(list(responses))
    app.dependency_overrides[get_llm] = lambda: llm
    return llm


def test_upload_extracts_and_persists_candidate(client: TestClient, db: Session) -> None:
    use_llm(VALID_CV)
    pdf = make_pdf(["Samira Ben Ali", "North Africa Finance - Data Engineer (mars 2022 - présent)"])

    response = client.post("/api/candidates/upload", files={"file": ("cv.pdf", pdf, "application/pdf")})

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["profile"]["identity"]["full_name"] == "Samira Ben Ali"
    assert body["profile"]["source_type"] == "cv"
    assert body["extraction"]["model"] == "fake-model"
    assert body["extraction"]["evidence"]["items"] > 0
    assert client.get(f"/api/candidates/{body['id']}").json()["id"] == body["id"]
    document = db.scalars(select(DocumentRecord)).one()
    assert document.raw_text is not None and "North Africa Finance" in document.raw_text
    assert document.purge_after is not None
    assert db.scalars(select(AuditLogRecord.action)).all() == ["candidate.extracted"]


def test_same_document_twice_is_a_conflict(client: TestClient) -> None:
    use_llm(VALID_CV, VALID_CV)
    pdf = make_pdf(["Samira Ben Ali", "Data Engineer at North Africa Finance since 2022"])

    first = client.post("/api/candidates/upload", files={"file": ("cv.pdf", pdf, "application/pdf")})
    second = client.post("/api/candidates/upload", files={"file": ("copy.pdf", pdf, "application/pdf")})

    assert second.status_code == 409
    assert second.json()["detail"]["existing_id"] == first.json()["id"]


def test_unsupported_file_is_rejected_before_any_llm_call(client: TestClient) -> None:
    llm = use_llm()

    response = client.post("/api/candidates/upload", files={"file": ("cv.exe", b"MZ\x90\x00", "application/pdf")})

    assert response.status_code == 415
    assert llm.sessions == []


def test_llm_outage_returns_503(client: TestClient) -> None:
    class DownLLM(FakeLLM):
        def session(self, **_: object) -> object:  # type: ignore[override]
            raise LLMError("could not reach the LLM API")

    app.dependency_overrides[get_llm] = lambda: DownLLM([])
    pdf = make_pdf(["Samira Ben Ali", "Data Engineer at North Africa Finance since 2022"])

    response = client.post("/api/candidates/upload", files={"file": ("cv.pdf", pdf, "application/pdf")})

    assert response.status_code == 503


def test_job_is_created_then_requirements_validated(client: TestClient) -> None:
    use_llm(VALID_JOB)

    created = client.post("/api/jobs", json={"text": JOB_TEXT})

    assert created.status_code == 201, created.text
    job = created.json()
    assert job["requirements_validated"] is False
    assert [s["verified"] for s in job["profile"]["skill_requirements"]] == [True, True]

    grid = job["profile"]
    grid["skill_requirements"][1]["requirement"] = "required"
    validated = client.put(f"/api/jobs/{job['id']}/requirements", json=grid)

    assert validated.status_code == 200, validated.text
    assert validated.json()["requirements_validated"] is True
    assert validated.json()["profile"]["skill_requirements"][1]["requirement"] == "required"


def test_unknown_candidate_is_404(client: TestClient) -> None:
    assert client.get("/api/candidates/00000000-0000-0000-0000-000000000000").status_code == 404
