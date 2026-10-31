"""Background CV reading for portal applications.

Tasks live in the database (`ingestion_tasks`), so they survive restarts and several API processes can share them:
a worker claims one with `FOR UPDATE SKIP LOCKED`, reads the CV, creates or updates the candidate and the
application, and records the outcome. The CV bytes are removed from the task once it is done or has failed.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import IngestionTaskRecord, JobRecord, TaskStatus, UserRecord, set_audit_scope
from app.extraction import ExtractionFailed, LLMClient, LLMError, LLMRefused
from app.ingestion import RejectedFile, UnreadableDocument
from app.services.portal import PortalError, candidate_of, create_portal_application, public_job
from app.services.privacy import set_consent
from app.services.profiles import DuplicateDocument, create_candidate_from_upload

log = logging.getLogger("app.tasks")

# Messages shown to the candidate when their CV cannot be used (no internal details).
UNREADABLE = "We could not read this file. Send a PDF or Word document with selectable text."
FAILED = "We could not process your CV. Please try again later."


def claim_next(db: Session) -> IngestionTaskRecord | None:
    task = db.scalar(
        select(IngestionTaskRecord)
        .where(IngestionTaskRecord.status == TaskStatus.QUEUED)
        .order_by(IngestionTaskRecord.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if task is None:
        return None
    task.status = TaskStatus.PROCESSING
    task.started_at = datetime.now(UTC)
    task.attempts += 1
    db.commit()
    return task


def _finish(db: Session, task: IngestionTaskRecord, status: TaskStatus, error: str | None = None) -> None:
    task.status = status
    task.error = error
    task.finished_at = datetime.now(UTC)
    task.content = None
    db.commit()


def process(db: Session, llm: LLMClient, settings: Settings, task: IngestionTaskRecord) -> None:
    """Read the task's CV into the user's candidate profile, then apply to the task's job if it is still open."""
    user = db.get(UserRecord, task.user_id) if task.user_id else None
    if user is None or task.content is None:
        _finish(db, task, TaskStatus.FAILED, FAILED)
        return
    job = db.get(JobRecord, task.job_id) if task.job_id else None
    set_audit_scope(db, job.organization_id if job else None)
    existing = candidate_of(db, user)
    try:
        candidate = create_candidate_from_upload(
            db, llm, settings, data=task.content, filename=task.filename, user_id=user.id, into=existing
        )
    except DuplicateDocument:
        db.rollback()
        if existing is None:
            _finish(db, task, TaskStatus.FAILED, "This CV was already submitted from another account.")
            return
        candidate = existing  # the same CV again: keep the profile as it is
    except (RejectedFile, UnreadableDocument, LLMRefused, ExtractionFailed):
        db.rollback()
        _finish(db, task, TaskStatus.FAILED, UNREADABLE)
        return
    except LLMError:
        db.rollback()
        if task.attempts < settings.ingestion_max_attempts:
            task.status = TaskStatus.QUEUED  # the model is unavailable: retry later
            db.commit()
        else:
            _finish(db, task, TaskStatus.FAILED, FAILED)
        return
    except Exception:
        db.rollback()
        log.exception("CV task %s failed", task.id)
        _finish(db, task, TaskStatus.FAILED, FAILED)
        return

    task.candidate_id = candidate.id
    if task.talent_pool_consent is not None:
        set_consent(db, candidate, task.talent_pool_consent, actor=user.actor)
    if job is not None:
        if public_job(db, job.id) is None:
            _finish(db, task, TaskStatus.FAILED, "This job is no longer open. Your profile was saved.")
            return
        with contextlib.suppress(PortalError):  # applied in the meantime with the existing profile
            create_portal_application(db, user, candidate, job)
    _finish(db, task, TaskStatus.DONE)


def run_once(session_factory: Callable[[], Session], llm: LLMClient, settings: Settings) -> bool:
    """Process one queued task, if any. Returns whether there was one."""
    with session_factory() as db:
        task = claim_next(db)
        if task is None:
            return False
        process(db, llm, settings, task)
        return True


def requeue_stale(db: Session) -> int:
    """Tasks left `processing` by a process that stopped mid-way go back to the queue (run at startup)."""
    stale = list(db.scalars(select(IngestionTaskRecord).where(IngestionTaskRecord.status == TaskStatus.PROCESSING)))
    for task in stale:
        task.status = TaskStatus.QUEUED
    db.commit()
    return len(stale)


class Worker:
    """A daemon thread polling the task table. One per API process; tasks are claimed safely across processes."""

    def __init__(
        self, session_factory: Callable[[], Session], llm: Callable[[], LLMClient], settings: Settings
    ) -> None:
        self._session_factory, self._llm, self._settings = session_factory, llm, settings
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="cv-worker", daemon=True)

    def start(self) -> None:
        with self._session_factory() as db:
            if count := requeue_stale(db):
                log.info("requeued %d interrupted CV task(s)", count)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if run_once(self._session_factory, self._llm(), self._settings):
                    continue
            except Exception:
                log.exception("CV worker iteration failed")
            self._stop.wait(self._settings.ingestion_poll_seconds)
