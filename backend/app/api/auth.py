"""Sign-up, sign-in and the signed-in user's own account."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.db import OrganizationStatus, Role
from app.services.accounts import (
    AccountError,
    LoginThrottled,
    authenticate,
    change_password,
    create_session,
    create_user,
    register_company,
    revoke_session,
)

from .deps import AppSettings, CurrentUser, DbSession, session_token
from .schemas import SessionOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=256)


class RegisterIn(BaseModel):
    account_type: Literal["candidate", "company"]
    email: str = Field(max_length=320)
    password: str = Field(max_length=256)
    full_name: str = Field(min_length=1, max_length=255)
    company_name: str | None = Field(None, max_length=255, description="Required for a company account.")
    job_title: str | None = Field(None, max_length=128)


class ProfileIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    job_title: str | None = Field(None, max_length=128)
    phone: str | None = Field(None, max_length=64)
    locale: Literal["en", "fr"] = "en"
    preferences: dict[str, Any] = Field(default_factory=dict, max_length=20)


class PasswordIn(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


def _session(db: DbSession, settings: AppSettings, user: Any) -> SessionOut:
    token, expires_at = create_session(db, user, ttl=timedelta(hours=settings.session_ttl_hours))
    return SessionOut(token=token, expires_at=expires_at, user=UserOut.from_record(user))


@router.post("/login")
def login(body: LoginIn, db: DbSession, settings: AppSettings) -> SessionOut:
    try:
        user = authenticate(db, body.email, body.password)
    except LoginThrottled as exc:
        raise HTTPException(429, "too many failed attempts; wait 15 minutes and try again") from exc
    if user is None:
        raise HTTPException(401, "incorrect email or password")
    return _session(db, settings, user)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: DbSession, settings: AppSettings) -> SessionOut:
    """Create a candidate account, or a company with its first recruiter (pending until an admin approves it)."""
    try:
        if body.account_type == "company":
            user = register_company(
                db,
                company_name=body.company_name or "",
                email=body.email,
                password=body.password,
                full_name=body.full_name,
                job_title=body.job_title,
            )
            if settings.auto_approve_companies and user.organization is not None:
                user.organization.status = OrganizationStatus.ACTIVE
        else:
            user = create_user(
                db, email=body.email, password=body.password, full_name=body.full_name, role=Role.CANDIDATE
            )
    except AccountError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    return _session(db, settings, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(db: DbSession, token: Annotated[str, Depends(session_token)]) -> Response:
    revoke_session(db, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return UserOut.from_record(user)


@router.patch("/me")
def update_me(body: ProfileIn, user: CurrentUser, db: DbSession) -> UserOut:
    user.full_name = body.full_name.strip()
    user.job_title = body.job_title or None
    user.phone = body.phone or None
    user.locale = body.locale
    user.preferences = body.preferences
    db.commit()
    return UserOut.from_record(user)


@router.post("/password")
def update_password(body: PasswordIn, user: CurrentUser, db: DbSession, settings: AppSettings) -> SessionOut:
    """Change the password. Every session is signed out; a new one is returned for this device."""
    try:
        change_password(db, user, current=body.current_password, new=body.new_password)
    except AccountError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _session(db, settings, user)
