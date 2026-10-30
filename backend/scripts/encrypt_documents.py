"""Encrypt stored documents with the current key, re-key them after a rotation, or decrypt them.

Usage (from backend/):
    uv run python -m app.security.crypto                 # print a new key
    DOCUMENT_ENCRYPTION_KEYS=<new>,<old> uv run python -m scripts.encrypt_documents
    uv run python -m scripts.encrypt_documents --decrypt # before a downgrade, or to drop encryption

Rotation: put the new key first and keep the old one after it, run this script, then remove the old key.
Works on the raw column bytes, so it handles plaintext, current-key and old-key rows alike. Idempotent.
"""

from __future__ import annotations

import argparse

from sqlalchemy import LargeBinary, column, select, table, update
from sqlalchemy.orm import Session

from app.db import get_engine
from app.security.crypto import get_cipher

documents = table("documents", column("id"), column("content", LargeBinary), column("raw_text", LargeBinary))


def run(db: Session, *, decrypt: bool = False) -> int:
    cipher = get_cipher()
    changed = 0
    for row in db.execute(select(documents.c.id, documents.c.content, documents.c.raw_text)).all():
        values = {}
        for name in ("content", "raw_text"):
            value = getattr(row, name)
            if value is None:
                continue
            value = bytes(value)
            new = cipher.decrypt(value) if decrypt else cipher.rotate(value)
            if new != value:
                values[name] = new
        if values:
            db.execute(update(documents).where(documents.c.id == row.id).values(**values))
            changed += 1
    db.commit()
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--decrypt", action="store_true", help="write every document back in plaintext")
    args = parser.parse_args()
    with Session(get_engine()) as session:
        print(f"{run(session, decrypt=args.decrypt)} document(s) updated")
