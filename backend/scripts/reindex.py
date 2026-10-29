"""Rebuild the retrieval index (embeddings + full-text) for every candidate and job.

Usage (from backend/):  uv run python -m scripts.reindex
Run after changing the embedding model, or after importing data outside the API.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import get_engine
from app.search.index import reindex_all

if __name__ == "__main__":
    with Session(get_engine()) as db:
        print(reindex_all(db))
