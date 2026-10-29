"""Parse application emails (RFC 822 / MIME) into body text and attachments."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser

TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Attachment:
    filename: str | None
    content_type: str
    data: bytes


@dataclass
class ParsedEmail:
    subject: str | None
    sender: str | None
    body_text: str
    attachments: list[Attachment] = field(default_factory=list)


def _html_to_text(markup: str) -> str:
    return html.unescape(TAG_RE.sub(" ", markup))


def parse_email(data: bytes) -> ParsedEmail:
    message = BytesParser(policy=policy.default).parsebytes(data)
    assert isinstance(message, EmailMessage)

    body_text = ""
    body = message.get_body(preferencelist=("plain", "html"))
    if body is not None:
        content = body.get_content()
        body_text = _html_to_text(content) if body.get_content_type() == "text/html" else content

    attachments = []
    for part in message.iter_attachments():
        payload = part.get_payload(decode=True)
        if isinstance(payload, bytes):
            attachments.append(
                Attachment(filename=part.get_filename(), content_type=part.get_content_type(), data=payload)
            )
    return ParsedEmail(
        subject=message.get("subject"),
        sender=message.get("from"),
        body_text=body_text.strip(),
        attachments=attachments,
    )
