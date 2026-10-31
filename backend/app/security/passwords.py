"""Password hashing with scrypt (standard library; memory-hard). Format: scrypt$n$r$p$salt$hash, base64 parts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

N, R, P = 2**14, 8, 1
MIN_LENGTH = 10


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=32)
    return f"scrypt${N}${R}${P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


def password_problem(password: str, *, email: str = "") -> str | None:
    """Why a new password is refused, or None. Length matters most; obvious choices are refused."""
    if len(password) < MIN_LENGTH:
        return f"the password must have at least {MIN_LENGTH} characters"
    if len(password) > 256:
        return "the password is too long"
    lowered = password.lower()
    if email and email.split("@")[0].lower() in lowered:
        return "the password must not contain your email address"
    if len(set(lowered)) < 4:
        return "the password is too repetitive"
    return None


# A hash to verify against when the email is unknown, so that timing does not reveal which accounts exist.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))
