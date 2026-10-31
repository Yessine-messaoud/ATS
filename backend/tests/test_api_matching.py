import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_llm
from app.db import AuditLogRecord, CandidateRecord, JobRecord, MatchRecord, OrganizationRecord, get_session
from app.main import app
from tests.conftest import FakeLLM

FIXTURES = Path(__file__).parents[1] / "eval" / "data" / "matching"


def load(kind: str, name: str) -> dict[str, object]:
    data: dict[str, object] = json.loads((FIXTURES / kind / f"{name}.json").read_text(encoding="utf-8"))
    return data


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_llm] = lambda: FakeLLM([None, None])  # explanations fall back to the template
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def pool(db: Session, org: OrganizationRecord) -> dict[str, CandidateRecord | JobRecord]:
    records: dict[str, CandidateRecord | JobRecord] = {}
    for name in ("en-01-data-engineer", "fr-01-analyste-bi", "en-03-adversarial"):
        records[name] = CandidateRecord(profile=load("candidates", name), schema_version="2", organization_id=org.id)
    profile = load("jobs", "job-01-data-engineer")
    records["job"] = JobRecord(title="Data Engineer", profile=profile, schema_version="2", organization_id=org.id)
    db.add_all(records.values())
    db.flush()
    return records


def test_ranking_orders_pool_and_separates_knocked_out(client: TestClient, pool: dict[str, object]) -> None:
    job = pool["job"]
    assert isinstance(job, JobRecord)

    ranking = client.get(f"/api/jobs/{job.id}/ranking").json()

    assert [r["display_name"] for r in ranking["ranked"]] == ["Samira Ben Ali", "Amira Gharbi"]
    assert ranking["ranked"][0]["overall_score"] > ranking["ranked"][1]["overall_score"]
    assert [r["display_name"] for r in ranking["knocked_out"]] == ["Karim Mansour"]
    assert ranking["knocked_out"][0]["knockouts"][0]["status"] == "fail"
    assert ranking["requirements_validated"] is False


def test_blind_ranking_hides_names(client: TestClient, pool: dict[str, object]) -> None:
    job = pool["job"]
    assert isinstance(job, JobRecord)

    ranking = client.get(f"/api/jobs/{job.id}/ranking", params={"blind": True}).json()

    names = [r["display_name"] for r in ranking["ranked"] + ranking["knocked_out"]]
    assert all(name.startswith("Candidate ") for name in names)


def test_match_is_persisted_with_explanation(client: TestClient, pool: dict[str, object], db: Session) -> None:
    candidate, job = pool["fr-01-analyste-bi"], pool["job"]
    assert isinstance(candidate, CandidateRecord) and isinstance(job, JobRecord)

    created = client.post("/api/matches", json={"candidate_id": str(candidate.id), "job_id": str(job.id)})

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["result"]["missing_required"] == ["Apache Spark"]
    assert body["result"]["explanation"]["source"] == "template"
    assert client.get(f"/api/matches/{body['id']}").json()["result"] == body["result"]
    record = db.scalars(select(MatchRecord)).one()
    assert record.engine_version == "match-v1"
    assert "match.scored" in db.scalars(select(AuditLogRecord.action)).all()


def test_job_weights_change_ranking_scores(client: TestClient, pool: dict[str, object]) -> None:
    job = pool["job"]
    assert isinstance(job, JobRecord)
    before = client.get(f"/api/jobs/{job.id}/ranking").json()["ranked"][1]["overall_score"]

    response = client.put(f"/api/jobs/{job.id}/weights", json={"required_skills": 100, "experience": 0})

    assert response.status_code == 200, response.text
    after = client.get(f"/api/jobs/{job.id}/ranking").json()
    assert after["weights"]["required_skills"] == 100
    assert after["ranked"][1]["overall_score"] != before
    assert (
        client.put(
            f"/api/jobs/{job.id}/weights",
            json=dict.fromkeys(
                [
                    "required_skills",
                    "preferred_skills",
                    "experience",
                    "seniority",
                    "languages",
                    "education",
                    "location",
                ],
                0,
            ),
        ).status_code
        == 422
    )


def test_recommendations_for_candidate(client: TestClient, pool: dict[str, object]) -> None:
    candidate = pool["en-01-data-engineer"]
    assert isinstance(candidate, CandidateRecord)

    recommendations = client.get(f"/api/candidates/{candidate.id}/recommendations").json()

    assert recommendations[0]["title"] == "Data Engineer"
    assert recommendations[0]["overall_score"] > 90


def test_unknown_ids_are_404(client: TestClient) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/api/jobs/{missing}/ranking").status_code == 404
    assert client.post("/api/matches", json={"candidate_id": missing, "job_id": missing}).status_code == 404
