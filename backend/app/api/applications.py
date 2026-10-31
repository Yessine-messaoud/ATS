from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.services.matching import score
from app.services.pipeline import AlreadyInPipeline, add_to_pipeline, move_application

from .deps import DbSession, StaffScope, get_or_404, get_scope
from .schemas import ApplicationIn, ApplicationOut, StageIn

router = APIRouter(prefix="/applications", tags=["pipeline"], dependencies=[Depends(get_scope)])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_application(body: ApplicationIn, db: DbSession, scope: StaffScope) -> ApplicationOut:
    """Add a candidate to a job's pipeline (stage `new`)."""
    candidate = get_or_404(lambda: scope.candidate(db, body.candidate_id), "candidate")
    job = get_or_404(lambda: scope.job(db, body.job_id), "job")
    try:
        application = add_to_pipeline(db, candidate, job, actor=scope.actor)
    except AlreadyInPipeline as exc:
        raise HTTPException(409, {"message": str(exc), "existing_id": str(exc.existing_id)}) from exc
    return ApplicationOut.build(application, result=score(candidate, job))


@router.patch("/{application_id}")
def change_stage(application_id: uuid.UUID, body: StageIn, db: DbSession, scope: StaffScope) -> ApplicationOut:
    """Move an application to another stage. Each move is recorded in the audit log as a human decision."""
    application = get_or_404(lambda: scope.application(db, application_id), "application")
    move_application(db, application, body.stage, actor=scope.actor, reason=body.reason)
    return ApplicationOut.build(application, result=score(application.candidate, application.job))
