from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select

from app.db import JobRecord, MatchRecord
from app.matching import MatchResult
from app.services.matching import create_match

from .deps import DbSession, Llm, StaffScope, get_or_404, get_scope

router = APIRouter(prefix="/matches", tags=["matching"], dependencies=[Depends(get_scope)])


class MatchIn(BaseModel):
    candidate_id: uuid.UUID
    job_id: uuid.UUID
    explain: bool = True


class MatchOut(BaseModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    job_id: uuid.UUID
    created_at: datetime
    result: MatchResult

    @classmethod
    def from_record(cls, record: MatchRecord) -> MatchOut:
        return cls(
            id=record.id,
            candidate_id=record.candidate_id,
            job_id=record.job_id,
            created_at=record.created_at,
            result=MatchResult.model_validate(record.factors),
        )


@router.post("", status_code=status.HTTP_201_CREATED)
def create(body: MatchIn, db: DbSession, llm: Llm, scope: StaffScope) -> MatchOut:
    """Score a candidate against a job and keep the result in the match history.

    The explanation uses the LLM when available (checked for faithfulness to the factors), else a template.
    """
    candidate = get_or_404(lambda: scope.candidate(db, body.candidate_id), "candidate")
    job = get_or_404(lambda: scope.job(db, body.job_id), "job")
    return MatchOut.from_record(create_match(db, candidate, job, llm=llm, with_explanation=body.explain))


@router.get("/{match_id}")
def get_match(match_id: uuid.UUID, db: DbSession, scope: StaffScope) -> MatchOut:
    query = (
        select(MatchRecord)
        .join(JobRecord, JobRecord.id == MatchRecord.job_id)
        .where(MatchRecord.id == match_id, scope.jobs())
    )
    return MatchOut.from_record(get_or_404(lambda: db.scalar(query), "match"))
