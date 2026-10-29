"""Turn an uploaded file into screened plain text."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.config import Settings

from .docx import DocxError, extract_docx_text
from .email_parser import parse_email
from .files import FileKind, InspectedFile, inspect_upload, sniff_kind
from .injection import detect_prompt_injection
from .pdf import PdfError, extract_pdf_text


class DocumentFlag(StrEnum):
    HIDDEN_TEXT = "hidden_text"
    POSSIBLE_PROMPT_INJECTION = "possible_prompt_injection"
    OCR_USED = "ocr_used"
    OCR_UNAVAILABLE = "ocr_unavailable"
    LOW_TEXT = "low_text"
    PAGES_TRUNCATED = "pages_truncated"
    NO_CV_ATTACHMENT = "no_cv_attachment"


class UnreadableDocument(ValueError):
    pass


@dataclass
class IngestedDocument:
    file: InspectedFile
    text: str
    flags: list[DocumentFlag] = field(default_factory=list)
    hidden_text: list[str] = field(default_factory=list)
    injection_snippets: list[str] = field(default_factory=list)


def _extract(kind: FileKind, data: bytes, settings: Settings, doc: IngestedDocument) -> str:
    if kind is FileKind.PDF:
        pdf = extract_pdf_text(
            data,
            max_pages=settings.max_pdf_pages,
            min_chars_per_page=settings.min_text_chars_per_page,
            ocr_languages=settings.ocr_languages,
        )
        doc.hidden_text.extend(pdf.hidden_text)
        if pdf.used_ocr:
            doc.flags.append(DocumentFlag.OCR_USED)
        if pdf.ocr_unavailable:
            doc.flags.append(DocumentFlag.OCR_UNAVAILABLE)
        if pdf.pages_read < pdf.page_count:
            doc.flags.append(DocumentFlag.PAGES_TRUNCATED)
        return pdf.text
    if kind is FileKind.DOCX:
        return extract_docx_text(data)
    if kind is FileKind.EMAIL:
        email = parse_email(data)
        parts = []
        for attachment in email.attachments:
            attachment_kind = sniff_kind(attachment.data)
            if attachment_kind in (FileKind.PDF, FileKind.DOCX):
                parts.append(_extract(attachment_kind, attachment.data, settings, doc))
        if not parts:
            doc.flags.append(DocumentFlag.NO_CV_ATTACHMENT)
        if email.body_text:
            parts.append(f"[Email message]\nSubject: {email.subject or ''}\n{email.body_text}")
        return "\n\n".join(parts)
    return data.decode("utf-8")


def ingest_document(data: bytes, settings: Settings) -> IngestedDocument:
    """Validate, extract text and screen it. Raises RejectedFile or UnreadableDocument."""
    inspected = inspect_upload(data, settings.max_upload_bytes)
    doc = IngestedDocument(file=inspected, text="")
    try:
        doc.text = _extract(inspected.kind, data, settings, doc).strip()
    except (PdfError, DocxError) as exc:
        raise UnreadableDocument(str(exc)) from exc

    if doc.hidden_text:
        doc.flags.append(DocumentFlag.HIDDEN_TEXT)
    doc.injection_snippets = detect_prompt_injection("\n".join([doc.text, *doc.hidden_text]))
    if doc.injection_snippets:
        doc.flags.append(DocumentFlag.POSSIBLE_PROMPT_INJECTION)
    if len(doc.text) < settings.min_text_chars_per_page:
        if not doc.text:
            raise UnreadableDocument("no readable text found in the document")
        doc.flags.append(DocumentFlag.LOW_TEXT)
    return doc
