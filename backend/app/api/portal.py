"""Public job board and the candidate's own space. Candidates see where they stand, never scores or rankings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import Text, cast, func, or_

from app.db import ApplicationRecord, AuditLogRecord, DocumentRecord, IngestionTaskRecord, JobRecord, TaskStatus
from app.models import CandidateProfile, JobProfile, RequirementKind
from app.security.passwords import verify_password
from app.services.portal import (
    CANDIDATE_STATUS,
    FINAL_STAGES,
    PortalError,
    applications_of,
    apply,
    candidate_of,
    correct_own_profile,
    own_application,
    pending_tasks,
    public_job,
    public_jobs_query,
    queue_cv,
    withdraw,
)
from app.services.privacy import erase_candidate, export_candidate, set_consent

from .deps import AppSettings, CandidateUser, DbSession, get_candidate_user, get_or_404
from .schemas import ConsentIn

public = APIRouter(prefix="/public", tags=["careers"])
router = APIRouter(prefix="/portal", tags=["candidate portal"], dependencies=[Depends(get_candidate_user)])


class CompanyOut(BaseModel):
    id: uuid.UUID
    name: str
    website: str | None
    industry: str | None
    size: str | None
    city: str | None
    description: str | None


class PublicJobOut(BaseModel):
    id: uuid.UUID
    title: str
    company: CompanyOut
    posted_at: datetime
    city: str | None
    country: str | None
    work_mode: str | None
    contract_type: str | None
    seniority: str | None
    required_skills: list[str]
    preferred_skills: list[str]
    min_years_experience: float | None

    @classmethod
    def build(cls, job: JobRecord) -> PublicJobOut:
        profile = JobProfile.model_validate(job.profile)
        assert job.organization is not None  # public jobs always belong to a company
        skills = profile.skill_requirements
        return cls(
            id=job.id,
            title=profile.title,
            company=CompanyOut.model_validate(job.organization, from_attributes=True),
            posted_at=job.created_at,
            city=profile.location.city if profile.location else None,
            country=profile.location.country if profile.location else None,
            work_mode=profile.work_mode.value if profile.work_mode else None,
            contract_type=profile.contract_type.value if profile.contract_type else None,
            seniority=profile.seniority.value if profile.seniority else None,
            required_skills=[s.name for s in skills if s.requirement is RequirementKind.REQUIRED],
            preferred_skills=[s.name for s in skills if s.requirement is not RequirementKind.REQUIRED],
            min_years_experience=profile.experience.minimum_years,
        )


class PublicJobDetailOut(PublicJobOut):
    description: str | None = Field(description="The job ad as the company wrote it.")
    responsibilities: list[str]
    benefits: list[str]
    languages: list[str]


class CvTaskOut(BaseModel):
    id: uuid.UUID
    status: TaskStatus
    job_id: uuid.UUID | None
    filename: str | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class PortalApplicationOut(BaseModel):
    id: uuid.UUID
    job: PublicJobOut
    status: str = Field(description="received, in_review, interview, offer, hired, not_selected or withdrawn.")
    status_label: str
    applied_at: datetime
    updated_at: datetime
    can_withdraw: bool

    @classmethod
    def build(cls, application: ApplicationRecord) -> PortalApplicationOut:
        key, label = CANDIDATE_STATUS[application.stage]
        return cls(
            id=application.id,
            job=PublicJobOut.build(application.job),
            status=key,
            status_label=label,
            applied_at=application.created_at,
            updated_at=application.updated_at,
            can_withdraw=application.stage not in FINAL_STAGES,
        )


class ApplyOut(BaseModel):
    """Either the application (profile already on file) or the CV task that will create it."""

    application: PortalApplicationOut | None = None
    task: CvTaskOut | None = None


class PortalProfileOut(BaseModel):
    candidate_id: uuid.UUID
    profile: CandidateProfile
    filename: str | None
    updated_at: datetime
    talent_pool_consent: bool | None
    unverified_items: int
    flags: list[str]


class DeleteAccountIn(BaseModel):
    password: str = Field(max_length=256)


# --- public careers page ----------------------------------------------------------------------------------------------


@public.get("/jobs")
def list_public_jobs(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100, description="Title, company, city or skill.")] = None,
    work_mode: str | None = None,
    contract_type: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[PublicJobOut]:
    query = public_jobs_query().limit(limit)
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.where(
            or_(func.lower(cast(JobRecord.profile, Text)).like(pattern), func.lower(JobRecord.title).like(pattern))
        )
    if work_mode:
        query = query.where(JobRecord.profile["work_mode"].astext == work_mode)
    if contract_type:
        query = query.where(JobRecord.profile["contract_type"].astext == contract_type)
    return [PublicJobOut.build(job) for job in db.scalars(query)]


@public.get("/jobs/{job_id}")
def get_public_job(job_id: uuid.UUID, db: DbSession) -> PublicJobDetailOut:
    job = get_or_404(lambda: public_job(db, job_id), "job")
    profile = JobProfile.model_validate(job.profile)
    document = db.get(DocumentRecord, job.source_document_id) if job.source_document_id else None
    return PublicJobDetailOut(
        **PublicJobOut.build(job).model_dump(),
        description=document.raw_text if document else None,
        responsibilities=profile.responsibilities,
        benefits=profile.benefits,
        languages=[
            f"{lang.language} ({lang.level.value})" if lang.level else lang.language
            for lang in profile.language_requirements
        ],
    )


@public.get("/companies/{organization_id}")
def get_public_company(organization_id: uuid.UUID, db: DbSession) -> list[PublicJobOut]:
    """A company's open jobs (empty if the company is unknown or not approved)."""
    return [
        PublicJobOut.build(j)
        for j in db.scalars(public_jobs_query().where(JobRecord.organization_id == organization_id))
    ]


# --- candidate space ------------------------------------------------------------------------------------------------


def _task_out(task: IngestionTaskRecord) -> CvTaskOut:
    return CvTaskOut.model_validate(task, from_attributes=True)


@router.get("/applications")
def my_applications(user: CandidateUser, db: DbSession) -> list[PortalApplicationOut]:
    return [PortalApplicationOut.build(a) for a in applications_of(db, user)]


@router.post("/applications", status_code=status.HTTP_202_ACCEPTED)
def apply_to_job(
    user: CandidateUser,
    db: DbSession,
    settings: AppSettings,
    job_id: Annotated[uuid.UUID, Form()],
    talent_pool_consent: Annotated[bool | None, Form()] = None,
    file: Annotated[UploadFile | None, File(description="CV (PDF, DOCX). Optional when a profile is on file.")] = None,
) -> ApplyOut:
    """Apply to a public job. A new CV is read in the background: follow its task, then the application appears."""
    job = get_or_404(lambda: public_job(db, job_id), "job")
    data = file.file.read(settings.max_upload_bytes + 1) if file is not None else None
    try:
        result = apply(
            db,
            settings,
            user,
            job,
            data=data,
            filename=file.filename if file else None,
            talent_pool_consent=talent_pool_consent,
        )
    except PortalError as exc:
        raise HTTPException(422, str(exc)) from exc
    if isinstance(result, IngestionTaskRecord):
        return ApplyOut(task=_task_out(result))
    return ApplyOut(application=PortalApplicationOut.build(result))


@router.post("/applications/{application_id}/withdraw")
def withdraw_application(application_id: uuid.UUID, user: CandidateUser, db: DbSession) -> PortalApplicationOut:
    application = get_or_404(lambda: own_application(db, user, application_id), "application")
    try:
        return PortalApplicationOut.build(withdraw(db, user, application))
    except PortalError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/tasks")
def my_tasks(user: CandidateUser, db: DbSession) -> list[CvTaskOut]:
    return [_task_out(t) for t in pending_tasks(db, user)]


def _profile_out(db: DbSession, user: CandidateUser) -> PortalProfileOut:
    candidate = get_or_404(lambda: candidate_of(db, user), "profile")
    document = db.get(DocumentRecord, candidate.source_document_id) if candidate.source_document_id else None
    evidence = candidate.extraction_meta.get("evidence") or {}
    return PortalProfileOut(
        candidate_id=candidate.id,
        profile=CandidateProfile.model_validate(candidate.profile),
        filename=document.filename if document else None,
        updated_at=candidate.updated_at,
        talent_pool_consent=candidate.talent_pool_consent,
        unverified_items=int(evidence.get("unverified", 0)) if isinstance(evidence, dict) else 0,
        flags=list(candidate.extraction_meta.get("document_flags") or []),
    )


@router.get("/profile")
def my_profile(user: CandidateUser, db: DbSession) -> PortalProfileOut:
    """What was read from the candidate's CV (404 until a CV has been read)."""
    return _profile_out(db, user)


@router.put("/profile")
def correct_my_profile(profile: CandidateProfile, user: CandidateUser, db: DbSession) -> PortalProfileOut:
    """Correct or remove what was read. Added or changed items are marked unverified: they earn no score."""
    candidate = get_or_404(lambda: candidate_of(db, user), "profile")
    correct_own_profile(db, user, candidate, profile)
    return _profile_out(db, user)


@router.post("/cv", status_code=status.HTTP_202_ACCEPTED)
def replace_cv(
    user: CandidateUser, db: DbSession, settings: AppSettings, file: Annotated[UploadFile, File()]
) -> CvTaskOut:
    """Send an updated CV: it replaces the profile once read. Applications are kept."""
    data = file.file.read(settings.max_upload_bytes + 1)
    try:
        task = queue_cv(db, settings, user, data=data, filename=file.filename, job=None, talent_pool_consent=None)
    except PortalError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _task_out(task)


@router.put("/consent")
def update_consent(body: ConsentIn, user: CandidateUser, db: DbSession) -> PortalProfileOut:
    """Let every company on the platform find the profile (talent pool), or only those applied to."""
    candidate = get_or_404(lambda: candidate_of(db, user), "profile")
    set_consent(db, candidate, body.consent, actor=user.actor)
    return _profile_out(db, user)


@router.get("/export")
def export_my_data(user: CandidateUser, db: DbSession, settings: AppSettings) -> JSONResponse:
    """Everything held about the candidate and their account, as a JSON download (GDPR access and portability)."""
    candidate = candidate_of(db, user)
    data = {
        "account": {
            "email": user.email,
            "full_name": user.full_name,
            "created_at": user.created_at.isoformat(),
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        },
        "candidate": export_candidate(db, candidate, settings) if candidate else None,
    }
    db.add(AuditLogRecord(actor=user.actor, action="candidate.exported", entity_type="user", entity_id=user.id))
    db.commit()
    return JSONResponse(data, headers={"Content-Disposition": 'attachment; filename="my-recruitai-data.json"'})


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(body: DeleteAccountIn, user: CandidateUser, db: DbSession) -> Response:
    """Erase the profile, CV, applications and the account itself. Irreversible; asks for the password."""
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(422, "the password is incorrect")
    candidate = candidate_of(db, user)
    if candidate is not None:
        erase_candidate(db, candidate, actor=user.actor, reason="deleted by the candidate")
    db.add(AuditLogRecord(actor=user.actor, action="user.deleted", entity_type="user", entity_id=user.id))
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
