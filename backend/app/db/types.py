"""Column types that encrypt on write and decrypt on read (see `app.security.crypto`)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import LargeBinary
from sqlalchemy.types import TypeDecorator

from app.security.crypto import get_cipher


class EncryptedBytes(TypeDecorator[bytes]):
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: bytes | None, dialect: Any) -> bytes | None:
        return None if value is None else get_cipher().encrypt(value)

    def process_result_value(self, value: bytes | None, dialect: Any) -> bytes | None:
        return None if value is None else get_cipher().decrypt(bytes(value))


class EncryptedText(TypeDecorator[str]):
    """Text stored as (possibly encrypted) UTF-8 bytes."""

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> bytes | None:
        return None if value is None else get_cipher().encrypt(value.encode("utf-8"))

    def process_result_value(self, value: bytes | None, dialect: Any) -> str | None:
        return None if value is None else get_cipher().decrypt(bytes(value)).decode("utf-8")
