"""Upload validation based on file content, never on the client-supplied name or MIME type."""

from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from enum import StrEnum

EMAIL_HEADER_PREFIXES = (b"received:", b"from:", b"return-path:", b"mime-version:", b"message-id:", b"delivered-to:")


class FileKind(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    TEXT = "text"
    EMAIL = "email"


MIME_TYPES = {
    FileKind.PDF: "application/pdf",
    FileKind.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    FileKind.TEXT: "text/plain",
    FileKind.EMAIL: "message/rfc822",
}


class RejectedFile(ValueError):
    """The upload is not an accepted document; `status_code` maps to the HTTP response."""

    def __init__(self, message: str, status_code: int = 415) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class InspectedFile:
    kind: FileKind
    mime_type: str
    size_bytes: int
    sha256: str


def _is_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return "word/document.xml" in archive.namelist()
    except zipfile.BadZipFile:
        return False


def _looks_like_email(data: bytes) -> bool:
    head = data[:2048].lstrip().lower()
    return head.startswith(EMAIL_HEADER_PREFIXES) and b"\n\n" in data.replace(b"\r\n", b"\n")


def _is_text(data: bytes) -> bool:
    try:
        decoded = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return "\x00" not in decoded


def sniff_kind(data: bytes) -> FileKind | None:
    if data.startswith(b"%PDF-"):
        return FileKind.PDF
    if data.startswith(b"PK\x03\x04"):
        return FileKind.DOCX if _is_docx(data) else None
    if _looks_like_email(data):
        return FileKind.EMAIL
    if _is_text(data):
        return FileKind.TEXT
    return None


def inspect_upload(data: bytes, max_bytes: int) -> InspectedFile:
    if not data:
        raise RejectedFile("empty file", status_code=422)
    if len(data) > max_bytes:
        raise RejectedFile(f"file exceeds the {max_bytes // (1024 * 1024)} MB limit", status_code=413)
    kind = sniff_kind(data)
    if kind is None:
        raise RejectedFile("unsupported file type; accepted: PDF, DOCX, plain text, email (.eml)")
    return InspectedFile(
        kind=kind, mime_type=MIME_TYPES[kind], size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()
    )
