"""Platform administration: companies, accounts, background tasks and system status. Admins only."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute

from app.db import (
    ApplicationRecord,
    AuditLogRecord,
    CandidateRecord,
    IngestionTaskRecord,
    JobRecord,
    OrganizationRecord,
    OrganizationStatus,
    Role,
    TaskStatus,
    UserRecord,
)
from app.providers import model_label
from app.security.crypto import get_cipher
from app.services.accounts import AccountError, create_user, revoke_all_sessions, set_password, temporary_password

from .deps import AdminUser, AppSettings, DbSession, get_admin, get_or_404
from .schemas import CreatedUserOut, OrganizationOut, UserOut

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_admin)])


class OverviewOut(BaseModel):
    organizations: dict[str, int]
    users: dict[str, int]
    jobs: int
    open_jobs: int
    candidates: int
    portal_candidates: int
    applications: int
    tasks: dict[str, int]
    llm_provider: str
    llm_model: str
    document_encryption: bool
    production_problems: list[str]


class OrganizationAdminOut(OrganizationOut):
    recruiters: int
    jobs: int
    open_jobs: int
    applications: int


class OrganizationStatusIn(BaseModel):
    status: OrganizationStatus


class UserIn(BaseModel):
    email: str = Field(max_length=320)
    full_name: str = Field(min_length=1, max_length=255)
    role: Literal["admin", "recruiter"]
    organization_id: uuid.UUID | None = None
    job_title: str | None = Field(None, max_length=128)


class UserPatchIn(BaseModel):
    is_active: bool


class AdminTaskOut(BaseModel):
    id: uuid.UUID
    status: TaskStatus
    filename: str | None
    job_id: uuid.UUID | None
    candidate_id: uuid.UUID | None
    attempts: int
    error: str | None
    created_at: datetime
    finished_at: datetime | None


def _counts(db: DbSession, column: InstrumentedAttribute[Any]) -> dict[str, int]:
    return {
        str(getattr(key, "value", key)): count
        for key, count in db.execute(select(column, func.count()).group_by(column))
    }


@router.get("/overview")
def overview(db: DbSession, settings: AppSettings) -> OverviewOut:
    def count(model: type, *where: ColumnElement[bool]) -> int:
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    return OverviewOut(
        organizations=_counts(db, OrganizationRecord.status),
        users=_counts(db, UserRecord.role),
        jobs=count(JobRecord),
        open_jobs=count(JobRecord, JobRecord.status == "open"),
        candidates=count(CandidateRecord),
        portal_candidates=count(CandidateRecord, CandidateRecord.user_id.is_not(None)),
        applications=count(ApplicationRecord),
        tasks=_counts(db, IngestionTaskRecord.status),
        llm_provider=settings.llm_provider,
        llm_model=model_label(settings),
        document_encryption=get_cipher().enabled,
        production_problems=settings.production_problems(),
    )


def _organization_out(db: DbSession, organization: OrganizationRecord) -> OrganizationAdminOut:
    jobs = select(JobRecord.id).where(JobRecord.organization_id == organization.id)
    return OrganizationAdminOut(
        **OrganizationOut.from_record(organization).model_dump(),
        recruiters=db.scalar(select(func.count()).where(UserRecord.organization_id == organization.id)) or 0,
        jobs=db.scalar(select(func.count()).select_from(jobs.subquery())) or 0,
        open_jobs=db.scalar(
            select(func.count()).where(JobRecord.organization_id == organization.id, JobRecord.status == "open")
        )
        or 0,
        applications=db.scalar(select(func.count()).where(ApplicationRecord.job_id.in_(jobs))) or 0,
    )


@router.get("/organizations")
def list_organizations(
    db: DbSession, status_filter: Annotated[OrganizationStatus | None, Query(alias="status")] = None
) -> list[OrganizationAdminOut]:
    query = select(OrganizationRecord).order_by(OrganizationRecord.created_at.desc())
    if status_filter is not None:
        query = query.where(OrganizationRecord.status == status_filter)
    return [_organization_out(db, o) for o in db.scalars(query)]


@router.patch("/organizations/{organization_id}")
def set_organization_status(
    organization_id: uuid.UUID, body: OrganizationStatusIn, db: DbSession, admin: AdminUser
) -> OrganizationAdminOut:
    """Approve, suspend or reinstate a company. Suspending signs its recruiters out and hides its jobs."""
    organization = get_or_404(lambda: db.get(OrganizationRecord, organization_id), "company")
    previous = organization.status
    organization.status = body.status
    if body.status is OrganizationStatus.SUSPENDED:
        for user in organization.users:
            revoke_all_sessions(db, user.id)
    db.add(
        AuditLogRecord(
            actor=admin.actor,
            action="organization.status_changed",
            entity_type="organization",
            entity_id=organization.id,
            organization_id=organization.id,
            details={"from": previous.value, "to": body.status.value},
        )
    )
    db.commit()
    return _organization_out(db, organization)


@router.get("/users")
def list_users(
    db: DbSession,
    role: Role | None = None,
    organization_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[UserOut]:
    query = select(UserRecord).order_by(UserRecord.created_at.desc()).limit(limit)
    if role is not None:
        query = query.where(UserRecord.role == role)
    if organization_id is not None:
        query = query.where(UserRecord.organization_id == organization_id)
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(UserRecord.full_name).like(pattern), UserRecord.email.like(pattern)))
    return [UserOut.from_record(u) for u in db.scalars(query)]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_staff_user(body: UserIn, db: DbSession) -> CreatedUserOut:
    """Create an admin, or a recruiter in a company. The temporary password is shown once."""
    organization = None
    if body.role == "recruiter":
        if body.organization_id is None:
            raise HTTPException(422, "choose the recruiter's company")
        organization = get_or_404(lambda: db.get(OrganizationRecord, body.organization_id), "company")
    password = temporary_password()
    try:
        user = create_user(
            db,
            email=body.email,
            password=password,
            full_name=body.full_name,
            role=Role(body.role),
            organization=organization,
            job_title=body.job_title,
        )
    except AccountError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return CreatedUserOut(user=UserOut.from_record(user), temporary_password=password)


@router.patch("/users/{user_id}")
def update_user(user_id: uuid.UUID, body: UserPatchIn, db: DbSession, admin: AdminUser) -> UserOut:
    """Deactivate (signs the user out everywhere) or reactivate an account."""
    user = get_or_404(lambda: db.get(UserRecord, user_id), "user")
    if user.id == admin.id and not body.is_active:
        raise HTTPException(422, "you cannot deactivate your own account")
    user.is_active = body.is_active
    if not body.is_active:
        revoke_all_sessions(db, user.id)
    db.add(
        AuditLogRecord(
            actor=admin.actor,
            action="user.activated" if body.is_active else "user.deactivated",
            entity_type="user",
            entity_id=user.id,
            organization_id=user.organization_id,
        )
    )
    db.commit()
    return UserOut.from_record(user)


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: uuid.UUID, db: DbSession) -> CreatedUserOut:
    """Replace the password with a temporary one (shown once) and sign the user out everywhere."""
    user = get_or_404(lambda: db.get(UserRecord, user_id), "user")
    password = temporary_password()
    try:
        set_password(db, user, password)
    except AccountError as exc:  # pragma: no cover - generated passwords always qualify
        raise HTTPException(500, str(exc)) from exc
    return CreatedUserOut(user=UserOut.from_record(user), temporary_password=password)


@router.get("/tasks")
def list_tasks(
    db: DbSession, status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None
) -> list[AdminTaskOut]:
    query = select(IngestionTaskRecord).order_by(IngestionTaskRecord.created_at.desc()).limit(100)
    if status_filter is not None:
        query = query.where(IngestionTaskRecord.status == status_filter)
    return [AdminTaskOut.model_validate(t, from_attributes=True) for t in db.scalars(query)]
