"""PDF text extraction with hidden-text detection and an optional OCR fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pymupdf

# Text a human reader cannot see. White is judged against the usual white page background.
NEAR_WHITE_CHANNEL = 0xF0
MIN_VISIBLE_FONT_SIZE = 3.0


class PdfError(ValueError):
    pass


@dataclass
class PdfText:
    text: str
    page_count: int
    pages_read: int
    hidden_text: list[str] = field(default_factory=list)
    used_ocr: bool = False
    ocr_unavailable: bool = False


def _is_near_white(color: int) -> bool:
    red, green, blue = (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF
    return min(red, green, blue) >= NEAR_WHITE_CHANNEL


def _hidden_reason(span: dict[str, Any], page_rect: pymupdf.Rect) -> str | None:
    if not span["text"].strip():
        return None
    if span.get("alpha", 255) == 0:
        return "transparent"
    if _is_near_white(span["color"]):
        return "white"
    if span["size"] < MIN_VISIBLE_FONT_SIZE:
        return "tiny"
    if not pymupdf.Rect(span["bbox"]).intersects(page_rect):
        return "off-page"
    return None


def _page_text(page: pymupdf.Page) -> tuple[str, list[str]]:
    visible_lines: list[str] = []
    hidden: list[str] = []
    # No clipping, so that text placed outside the page is seen (and reported) rather than silently dropped.
    for block in page.get_text("dict", clip=pymupdf.INFINITE_RECT())["blocks"]:
        for line in block.get("lines", []):
            visible_spans: list[str] = []
            for span in line["spans"]:
                reason = _hidden_reason(span, page.rect)
                if reason is None:
                    visible_spans.append(span["text"])
                elif span["text"].strip():
                    hidden.append(f"[{reason}] {span['text'].strip()}")
            if visible_spans:
                visible_lines.append("".join(visible_spans))
        visible_lines.append("")
    return "\n".join(visible_lines).strip(), hidden


def _ocr_page(page: pymupdf.Page, languages: str) -> str:
    textpage = page.get_textpage_ocr(language=languages, full=True)
    return str(page.get_text("text", textpage=textpage)).strip()


def extract_pdf_text(data: bytes, *, max_pages: int, min_chars_per_page: int, ocr_languages: str) -> PdfText:
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError) as exc:
        raise PdfError("the PDF is corrupted or unreadable") from exc

    with document:
        if document.needs_pass:
            raise PdfError("password-protected PDFs are not accepted")
        result = PdfText(text="", page_count=document.page_count, pages_read=min(document.page_count, max_pages))
        page_texts: list[str] = []
        for page in document.pages(0, result.pages_read):
            text, hidden = _page_text(page)
            result.hidden_text.extend(hidden)
            if len(text) < min_chars_per_page and not result.ocr_unavailable:
                try:
                    ocr_text = _ocr_page(page, ocr_languages)
                except RuntimeError:
                    # Tesseract is not installed or has no data for these languages.
                    result.ocr_unavailable = True
                else:
                    if len(ocr_text) > len(text):
                        text, result.used_ocr = ocr_text, True
            page_texts.append(text)
        result.text = "\n\n".join(t for t in page_texts if t)
    return result
