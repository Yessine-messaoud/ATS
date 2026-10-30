"""Apply the retention policy: purge expired document content and erase inactive, non-consenting candidates.

Usage (from backend/):  uv run python -m scripts.retention [--dry-run]
Schedule it daily (cron, a Kubernetes CronJob, or Windows Task Scheduler). Every purge and erasure is audited.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_engine
from app.services.privacy import run_retention

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report what would be purged, change nothing")
    args = parser.parse_args()
    with Session(get_engine()) as db:
        report = run_retention(db, get_settings(), dry_run=args.dry_run)
    print(json.dumps({"dry_run": args.dry_run, **asdict(report)}, indent=2))
