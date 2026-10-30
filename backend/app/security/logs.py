"""Keep personal data out of logs.

Application code logs ids, never names or contact details. This filter is the safety net for everything else
(library messages, exception text that quotes a CV): e-mail addresses and phone numbers are masked in every record
that reaches the root handlers.
"""

from __future__ import annotations

import logging
import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
# International or national numbers with separators; needs 8+ digits so that ids, years and counts are left alone.
PHONE = re.compile(r"(?<![\w-])\+?\d[\d .()-]{6,}\d(?![\w-])")


def redact(text: str) -> str:
    text = EMAIL.sub("[email]", text)
    return PHONE.sub(lambda m: "[phone]" if sum(c.isdigit() for c in m.group()) >= 8 else m.group(), text)


class PiiFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = redact(message)
        if redacted != message:
            record.msg, record.args = redacted, None
        if record.exc_info and record.exc_info[1] is not None:
            # Exception text can quote document content: keep the traceback, redacted.
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


def install_pii_filter() -> None:
    pii_filter = PiiFilter()
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "app", "sqlalchemy"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, PiiFilter) for f in logger.filters):
            logger.addFilter(pii_filter)
        for handler in logger.handlers:
            if not any(isinstance(f, PiiFilter) for f in handler.filters):
                handler.addFilter(pii_filter)
