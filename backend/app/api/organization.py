"""The recruiter's company: its public profile and its team."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db import AuditLogRecord, OrganizationRecord, Role, UserRecord
from app.services.accounts import AccountError, create_user, revoke_all_sessions, temporary_password

from .deps import DbSession, RecruiterUser, get_or_404, get_recruiter
from .schemas import CreatedUserOut, OrganizationOut, UserOut

router = APIRouter(prefix="/organization", tags=["company"], dependencies=[Depends(get_recruiter)])


class OrganizationIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    website: str | None = Field(None, max_length=255)
    industry: str | None = Field(None, max_length=128)
    size: str | None = Field(None, max_length=32)
    city: str | None = Field(None, max_length=128)
    description: str | None = Field(None, max_length=4000)


class MemberIn(BaseModel):
    email: str = Field(max_length=320)
    full_name: str = Field(min_length=1, max_length=255)
    job_title: str | None = Field(None, max_length=128)


class MemberPatchIn(BaseModel):
    is_active: bool


def _organization(user: UserRecord) -> OrganizationRecord:
    assert user.organization is not None  # guaranteed by get_recruiter
    return user.organization


@router.get("")
def get_organization(user: RecruiterUser) -> OrganizationOut:
    return OrganizationOut.from_record(_organization(user))


@router.put("")
def update_organization(body: OrganizationIn, user: RecruiterUser, db: DbSession) -> OrganizationOut:
    """The company profile shown to candidates on the careers page."""
    organization = _organization(user)
    for field, value in body.model_dump().items():
        setattr(organization, field, value.strip() if isinstance(value, str) and value.strip() else None)
    organization.name = body.name.strip()
    db.add(
        AuditLogRecord(
            actor=user.actor, action="organization.updated", entity_type="organization", entity_id=organization.id
        )
    )
    db.commit()
    return OrganizationOut.from_record(organization)


@router.get("/members")
def list_members(user: RecruiterUser, db: DbSession) -> list[UserOut]:
    members = db.scalars(
        select(UserRecord).where(UserRecord.organization_id == user.organization_id).order_by(UserRecord.full_name)
    )
    return [UserOut.from_record(m) for m in members]


@router.post("/members", status_code=status.HTTP_201_CREATED)
def add_member(body: MemberIn, user: RecruiterUser, db: DbSession) -> CreatedUserOut:
    """Add a recruiter to the company. The temporary password is shown once."""
    password = temporary_password()
    try:
        member = create_user(
            db,
            email=body.email,
            password=password,
            full_name=body.full_name,
            role=Role.RECRUITER,
            organization=_organization(user),
            job_title=body.job_title,
        )
    except AccountError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return CreatedUserOut(user=UserOut.from_record(member), temporary_password=password)


@router.patch("/members/{member_id}")
def update_member(member_id: uuid.UUID, body: MemberPatchIn, user: RecruiterUser, db: DbSession) -> UserOut:
    query = select(UserRecord).where(UserRecord.id == member_id, UserRecord.organization_id == user.organization_id)
    member = get_or_404(lambda: db.scalar(query), "team member")
    if member.id == user.id:
        raise HTTPException(422, "you cannot deactivate your own account")
    member.is_active = body.is_active
    if not body.is_active:
        revoke_all_sessions(db, member.id)
    db.add(
        AuditLogRecord(
            actor=user.actor,
            action="user.activated" if body.is_active else "user.deactivated",
            entity_type="user",
            entity_id=member.id,
        )
    )
    db.commit()
    return UserOut.from_record(member)
