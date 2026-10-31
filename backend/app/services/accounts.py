"""Accounts and sign-in sessions.

Sessions are opaque random tokens; the database keeps only their SHA-256, so reading the table does not let anyone
sign in. The Next.js server keeps the token in an httpOnly cookie and sends it as a bearer token: browsers never
see it in JavaScript and never call this API directly.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import AuditLogRecord, OrganizationRecord, OrganizationStatus, Role, SessionRecord, UserRecord
from app.security.passwords import DUMMY_HASH, hash_password, password_problem, verify_password


class AccountError(ValueError):
    """A refused account operation; the message is safe to show to the user."""


class LoginThrottled(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _audit(db: Session, user: UserRecord, action: str, **details: object) -> None:
    db.add(
        AuditLogRecord(
            actor=user.actor,
            action=action,
            entity_type="user",
            entity_id=user.id,
            details=details,
            organization_id=user.organization_id,
        )
    )


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    role: Role,
    organization: OrganizationRecord | None = None,
    job_title: str | None = None,
) -> UserRecord:
    email = normalize_email(email)
    if "@" not in email or len(email) > 320:
        raise AccountError("enter a valid email address")
    if not full_name.strip():
        raise AccountError("enter your name")
    if role is Role.RECRUITER and organization is None:
        raise AccountError("a recruiter belongs to a company")
    if role is not Role.RECRUITER and organization is not None:
        raise AccountError("only recruiters belong to a company")
    if problem := password_problem(password, email=email):
        raise AccountError(problem)
    if db.scalar(select(UserRecord.id).where(UserRecord.email == email)) is not None:
        raise AccountError("an account already exists with this email")
    user = UserRecord(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        role=role,
        organization=organization,
        organization_id=organization.id if organization else None,
        job_title=job_title,
        locale="en",
        preferences={},
        is_active=True,
    )
    db.add(user)
    db.flush()
    _audit(db, user, "user.created", role=role.value)
    return user


def register_company(
    db: Session, *, company_name: str, email: str, password: str, full_name: str, job_title: str | None = None
) -> UserRecord:
    """A company signs up: it starts pending, and its jobs are not public until a platform admin approves it."""
    if not company_name.strip():
        raise AccountError("enter the company name")
    organization = OrganizationRecord(name=company_name.strip(), status=OrganizationStatus.PENDING)
    db.add(organization)
    db.flush()
    return create_user(
        db,
        email=email,
        password=password,
        full_name=full_name,
        role=Role.RECRUITER,
        organization=organization,
        job_title=job_title,
    )


class _Throttle:
    """At most `limit` failed sign-ins per email in `window` seconds (per API process)."""

    def __init__(self, limit: int = 5, window: float = 15 * 60) -> None:
        self.limit, self.window = limit, window
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _recent(self, key: str) -> deque[float]:
        failures = self._failures[key]
        while failures and failures[0] < time.monotonic() - self.window:
            failures.popleft()
        return failures

    def check(self, key: str) -> None:
        with self._lock:
            if len(self._recent(key)) >= self.limit:
                raise LoginThrottled

    def fail(self, key: str) -> None:
        with self._lock:
            self._recent(key).append(time.monotonic())

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


throttle = _Throttle()


def authenticate(db: Session, email: str, password: str) -> UserRecord | None:
    """The active user with these credentials, or None. Raises LoginThrottled after repeated failures."""
    key = normalize_email(email)
    throttle.check(key)
    user = db.scalar(select(UserRecord).where(UserRecord.email == key))
    # Always verify against a hash so that response time does not tell which emails have an account.
    valid = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if user is None or not valid or not user.is_active or _suspended(user):
        throttle.fail(key)
        return None
    throttle.clear(key)
    user.last_login_at = datetime.now(UTC)
    return user


def _suspended(user: UserRecord) -> bool:
    return user.organization is not None and user.organization.status is OrganizationStatus.SUSPENDED


def create_session(db: Session, user: UserRecord, *, ttl: timedelta) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + ttl
    db.add(SessionRecord(user_id=user.id, token_hash=_token_hash(token), expires_at=expires_at))
    db.execute(delete(SessionRecord).where(SessionRecord.user_id == user.id, SessionRecord.expires_at < func.now()))
    _audit(db, user, "user.signed_in")
    db.commit()
    return token, expires_at


def user_for_token(db: Session, token: str) -> UserRecord | None:
    session = db.scalar(
        select(SessionRecord).where(
            SessionRecord.token_hash == _token_hash(token), SessionRecord.expires_at > func.now()
        )
    )
    if session is None or not session.user.is_active or _suspended(session.user):
        return None
    return session.user


def revoke_session(db: Session, token: str) -> None:
    db.execute(delete(SessionRecord).where(SessionRecord.token_hash == _token_hash(token)))
    db.commit()


def revoke_all_sessions(db: Session, user_id: uuid.UUID) -> None:
    db.execute(delete(SessionRecord).where(SessionRecord.user_id == user_id))


def change_password(db: Session, user: UserRecord, *, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        raise AccountError("the current password is incorrect")
    set_password(db, user, new)


def set_password(db: Session, user: UserRecord, password: str) -> None:
    if problem := password_problem(password, email=user.email):
        raise AccountError(problem)
    user.password_hash = hash_password(password)
    revoke_all_sessions(db, user.id)
    _audit(db, user, "user.password_changed")
    db.commit()


def temporary_password() -> str:
    """For accounts created by someone else; shown once, to be changed after the first sign-in."""
    return secrets.token_urlsafe(12)
