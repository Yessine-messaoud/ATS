"""Render the synthetic CV texts as PDFs, so the eval exercises the real ingestion path."""

from __future__ import annotations

import textwrap

import pymupdf

FONT_SIZE = 10
LINE_HEIGHT = 13
MARGIN = 56
WRAP_CHARS = 95
# The built-in Helvetica covers Latin-1 (é, ç, ...) but not typographic punctuation.
PUNCTUATION = str.maketrans(
    {
        "—": "-",  # em dash
        "–": "-",  # en dash
        "•": "-",  # bullet
        "·": "-",  # middle dot
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
    }
)


def pdf_safe(text: str) -> str:
    return text.translate(PUNCTUATION)


def render_pdf(text: str, *, hidden_lines: list[str] | None = None) -> bytes:
    """One or more A4 pages of wrapped text; `hidden_lines` are drawn in white at the bottom of page 1."""
    lines: list[str] = []
    for raw in pdf_safe(text).splitlines():
        lines.extend(textwrap.wrap(raw, WRAP_CHARS) or [""])

    document = pymupdf.open()
    per_page = int((pymupdf.paper_rect("a4").height - 2 * MARGIN) // LINE_HEIGHT)
    for start in range(0, len(lines), per_page):
        page = document.new_page(width=pymupdf.paper_rect("a4").width, height=pymupdf.paper_rect("a4").height)
        for offset, line in enumerate(lines[start : start + per_page]):
            page.insert_text((MARGIN, MARGIN + offset * LINE_HEIGHT), line, fontsize=FONT_SIZE, fontname="helv")
    first = document[0]
    for index, hidden in enumerate(hidden_lines or []):
        point = (MARGIN, first.rect.height - MARGIN + index * 8)
        first.insert_text(point, pdf_safe(hidden), fontsize=6, fontname="helv", color=(1, 1, 1))
    data: bytes = document.tobytes()
    document.close()
    return data
