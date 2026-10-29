"""Load the synthetic demo data set (6 candidates, 3 jobs, a small pipeline) without calling the LLM.

Usage (from backend/):  uv run python -m scripts.seed_demo
Idempotent: documents already present (same SHA-256) are skipped.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import ApplicationRecord, ApplicationStage, CandidateRecord, DocumentRecord, JobRecord, get_engine
from app.extraction.evidence import verify_evidence
from app.ingestion import ingest_document
from app.ingestion.pipeline import DocumentFlag
from app.models import CandidateProfile, JobProfile, SourceType
from app.search.index import reindex_all
from eval.render import render_pdf

EVAL = Path(__file__).parents[1] / "eval" / "data"
# (job, candidate, stage) triples placed in the demo pipeline.
PIPELINE = [
    ("job-01-data-engineer", "en-01-data-engineer", ApplicationStage.INTERVIEW),
    ("job-01-data-engineer", "fr-01-analyste-bi", ApplicationStage.SCREENING),
    ("job-01-data-engineer", "en-02-ml-engineer", ApplicationStage.NEW),
    ("job-03-stage-pfe", "fr-03-stagiaire-web", ApplicationStage.NEW),
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _existing(db: Session, sha: str) -> DocumentRecord | None:
    return db.scalar(select(DocumentRecord).where(DocumentRecord.sha256 == sha))


def seed(db: Session) -> dict[str, int]:
    settings = Settings()
    created = {"candidates": 0, "jobs": 0, "applications": 0}
    candidates: dict[str, CandidateRecord] = {}
    jobs: dict[str, JobRecord] = {}

    for fixture in sorted((EVAL / "matching" / "candidates").glob("*.json")):
        cv_text = (EVAL / "cvs" / f"{fixture.stem}.txt").read_text(encoding="utf-8")
        gold = json.loads((EVAL / "cvs" / f"{fixture.stem}.gold.json").read_text(encoding="utf-8"))
        pdf = render_pdf(cv_text, hidden_lines=gold.get("hidden_text"))
        document = _existing(db, _sha(pdf))
        if document is not None:
            found = db.scalar(select(CandidateRecord).where(CandidateRecord.source_document_id == document.id))
            if found is not None:
                candidates[fixture.stem] = found
            continue

        ingested = ingest_document(pdf, settings)
        profile = CandidateProfile.model_validate_json(fixture.read_text(encoding="utf-8"))
        profile.source_type = SourceType.CV
        evidence = verify_evidence(profile, ingested.text)
        document = DocumentRecord(
            kind="pdf",
            filename=f"{fixture.stem}.pdf",
            mime_type="application/pdf",
            size_bytes=len(pdf),
            sha256=_sha(pdf),
            content=pdf,
            raw_text=ingested.text,
            flags=[flag.value for flag in ingested.flags if flag is not DocumentFlag.OCR_UNAVAILABLE],
        )
        db.add(document)
        db.flush()
        candidate = CandidateRecord(
            profile=profile.model_dump(mode="json"),
            schema_version=profile.schema_version,
            email=profile.identity.email,
            source_document_id=document.id,
            extraction_meta={
                "model": "demo-seed",
                "prompt_version": "fixture",
                "issues": [],
                "evidence": {"items": evidence.items, "verified": evidence.verified, "unverified": evidence.unverified},
                "document_flags": document.flags,
                "hidden_text": ingested.hidden_text,
                "injection_snippets": ingested.injection_snippets,
            },
        )
        db.add(candidate)
        candidates[fixture.stem] = candidate
        created["candidates"] += 1

    for fixture in sorted((EVAL / "matching" / "jobs").glob("*.json")):
        text = (EVAL / "jobs" / f"{fixture.stem}.txt").read_text(encoding="utf-8")
        document = _existing(db, _sha(text.encode()))
        if document is not None:
            found_job = db.scalar(select(JobRecord).where(JobRecord.source_document_id == document.id))
            if found_job is not None:
                jobs[fixture.stem] = found_job
            continue
        profile_job = JobProfile.model_validate_json(fixture.read_text(encoding="utf-8"))
        verify_evidence(profile_job, text)
        document = DocumentRecord(
            kind="job_description",
            mime_type="text/plain",
            size_bytes=len(text.encode()),
            sha256=_sha(text.encode()),
            raw_text=text,
        )
        db.add(document)
        db.flush()
        job = JobRecord(
            title=profile_job.title,
            profile=profile_job.model_dump(mode="json"),
            schema_version=profile_job.schema_version,
            requirements_validated=fixture.stem == "job-01-data-engineer",
            source_document_id=document.id,
            extraction_meta={"model": "demo-seed", "prompt_version": "fixture"},
        )
        db.add(job)
        jobs[fixture.stem] = job
        created["jobs"] += 1
    db.flush()

    for job_name, candidate_name, stage in PIPELINE:
        pipeline_job, pipeline_candidate = jobs.get(job_name), candidates.get(candidate_name)
        if pipeline_job is None or pipeline_candidate is None:
            continue
        exists = db.scalar(
            select(ApplicationRecord).where(
                ApplicationRecord.job_id == pipeline_job.id, ApplicationRecord.candidate_id == pipeline_candidate.id
            )
        )
        if exists is None:
            db.add(ApplicationRecord(job_id=pipeline_job.id, candidate_id=pipeline_candidate.id, stage=stage))
            created["applications"] += 1
    db.commit()
    reindex_all(db)
    return created


def main() -> None:
    with Session(get_engine()) as db:
        print(seed(db))


if __name__ == "__main__":
    main()
