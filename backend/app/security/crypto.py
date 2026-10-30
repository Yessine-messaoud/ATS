"""Encryption at rest for candidate documents (original file and extracted text).

Fernet (AES-128-CBC + HMAC-SHA256) with key rotation: DOCUMENT_ENCRYPTION_KEYS is a comma-separated list, the first
key encrypts, all of them decrypt. Ciphertexts carry a prefix, so rows written before a key was configured stay
readable (as plaintext) and `scripts.encrypt_documents` can encrypt or re-key them later.

Without a key, documents are stored in plaintext; that is refused in production (see `check_production_settings`).
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.config import get_settings

PREFIX = b"enc:v1:"


class DecryptionError(RuntimeError):
    pass


class DocumentCipher:
    def __init__(self, keys: list[str]):
        fernets = [Fernet(key.encode()) for key in keys]
        self._primary = fernets[0] if fernets else None
        self._fernet = MultiFernet(fernets) if fernets else None

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def encrypt(self, data: bytes) -> bytes:
        if self._fernet is None:
            return data
        return PREFIX + self._fernet.encrypt(data)

    def decrypt(self, data: bytes) -> bytes:
        if not is_encrypted(data):
            return data
        if self._fernet is None:
            raise DecryptionError("document is encrypted but DOCUMENT_ENCRYPTION_KEYS is not set")
        try:
            return self._fernet.decrypt(data[len(PREFIX) :])
        except InvalidToken as exc:
            raise DecryptionError("document was encrypted with a key that is no longer configured") from exc

    def rotate(self, data: bytes) -> bytes:
        """Encrypt a plaintext value, or re-encrypt one written with an older key; current ones are unchanged."""
        if self._fernet is None or self._primary is None:
            raise DecryptionError("no encryption key configured")
        if not is_encrypted(data):
            return self.encrypt(data)
        try:
            self._primary.decrypt(data[len(PREFIX) :])
            return data
        except InvalidToken:
            pass
        try:
            return PREFIX + self._fernet.rotate(data[len(PREFIX) :])
        except InvalidToken as exc:
            raise DecryptionError("document was encrypted with a key that is no longer configured") from exc


def is_encrypted(data: bytes) -> bool:
    return data.startswith(PREFIX)


def generate_key() -> str:
    return Fernet.generate_key().decode()


def parse_keys(value: str | None) -> list[str]:
    return [key.strip() for key in (value or "").split(",") if key.strip()]


@lru_cache
def get_cipher() -> DocumentCipher:
    return DocumentCipher(parse_keys(get_settings().document_encryption_keys))


if __name__ == "__main__":
    print(generate_key())
