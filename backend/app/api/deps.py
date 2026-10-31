"""Shared FastAPI dependencies and error mapping."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import Role, UserRecord, get_session, set_audit_scope
from app.extraction import ExtractionFailed, LLMClient, LLMError, LLMRefused
from app.ingestion import RejectedFile, UnreadableDocument
from app.providers import make_llm
from app.services.access import Scope
from app.services.accounts import user_for_token
from app.services.profiles import DuplicateDocument


@lru_cache
def get_llm() -> LLMClient:
    return make_llm(get_settings())


DbSession = Annotated[Session, Depends(get_session)]
Llm = Annotated[LLMClient, Depends(get_llm)]
AppSettings = Annotated[Settings, Depends(get_settings)]

bearer = HTTPBearer(auto_error=False, description="Session token from POST /api/auth/login.")


def session_token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> str:
    if credentials is None:
        raise HTTPException(401, "sign in required", headers={"WWW-Authenticate": "Bearer"})
    return credentials.credentials


def get_current_user(db: DbSession, token: Annotated[str, Depends(session_token)]) -> UserRecord:
    user = user_for_token(db, token)
    if user is None:
        raise HTTPException(401, "your session has expired; sign in again", headers={"WWW-Authenticate": "Bearer"})
    # Audit entries written during this request belong to the user's company.
    set_audit_scope(db, user.organization_id)
    return user


CurrentUser = Annotated[UserRecord, Depends(get_current_user)]


def get_scope(user: CurrentUser) -> Scope:
    """Staff only: platform admins and company recruiters."""
    if user.role not in (Role.ADMIN, Role.RECRUITER):
        raise HTTPException(403, "this area is for recruiters")
    return Scope(user)


def get_admin(user: CurrentUser) -> UserRecord:
    if user.role is not Role.ADMIN:
        raise HTTPException(403, "this area is for platform administrators")
    return user


def get_recruiter(user: CurrentUser) -> UserRecord:
    if user.role is not Role.RECRUITER or user.organization is None:
        raise HTTPException(403, "this action is for company recruiters")
    return user


def get_candidate_user(user: CurrentUser) -> UserRecord:
    if user.role is not Role.CANDIDATE:
        raise HTTPException(403, "this area is for candidates")
    return user


StaffScope = Annotated[Scope, Depends(get_scope)]
AdminUser = Annotated[UserRecord, Depends(get_admin)]
RecruiterUser = Annotated[UserRecord, Depends(get_recruiter)]
CandidateUser = Annotated[UserRecord, Depends(get_candidate_user)]


@contextmanager
def domain_errors() -> Iterator[None]:
    """Translate ingestion, extraction and duplicate errors into HTTP responses."""
    try:
        yield
    except RejectedFile as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except UnreadableDocument as exc:
        raise HTTPException(422, str(exc)) from exc
    except DuplicateDocument as exc:
        raise HTTPException(409, {"message": str(exc), "existing_id": str(exc.existing_id)}) from exc
    except LLMRefused as exc:
        raise HTTPException(422, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(503, f"AI service unavailable: {exc}") from exc
    except ExtractionFailed as exc:
        raise HTTPException(502, f"extraction failed: {exc}") from exc


def get_or_404[T](getter: Callable[[], T | None], what: str) -> T:
    value = getter()
    if value is None:
        raise HTTPException(404, f"{what} not found")
    return value
