"""Minimal DOCX text extraction from word/document.xml (paragraphs and table cells)."""

from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_DOCUMENT_XML_BYTES = 20 * 1024 * 1024


class DocxError(ValueError):
    pass


def extract_docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > MAX_DOCUMENT_XML_BYTES:
                raise DocxError("document.xml is too large")
            xml = archive.read(info)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise DocxError("the DOCX file is corrupted") from exc

    # The XML comes from the upload: ElementTree does not resolve external entities.
    root = ElementTree.fromstring(xml)
    paragraphs = []
    for paragraph in root.iter(f"{WORD_NS}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{WORD_NS}t"))
        if text.strip():
            paragraphs.append(text)
    return "\n".join(paragraphs)
