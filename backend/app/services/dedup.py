"""Duplicate candidate detection and recruiter-confirmed merges.

The same person often applies twice (email + form, or an updated CV). Duplicates are only *suggested*: merging is
always a human decision, recorded in the audit log.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from rapidfuzz import fuzz
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import ApplicationRecord, AuditLogRecord, CandidateRecord, CandidateSearchRecord, MatchRecord
from app.matching.skills import normalize_text
from app.models import CandidateProfile

PHONE_DIGITS = 8
NAME_MATCH = 90
PROFILE_SIMILARITY = 0.9


@dataclass(frozen=True)
class DuplicateCandidate:
    candidate_id: uuid.UUID
    reasons: list[str]


def _phone_key(phone: str | None) -> str | None:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-PHONE_DIGITS:] if len(digits) >= PHONE_DIGITS else None


def _email_key(email: str | None) -> str | None:
    return email.strip().lower() if email else None


def find_duplicates(db: Session, candidate: CandidateRecord) -> list[DuplicateCandidate]:
    profile = CandidateProfile.model_validate(candidate.profile)
    email, phone = _email_key(profile.identity.email), _phone_key(profile.identity.phone)
    name = normalize_text(profile.identity.full_name or "")
    own_index = db.get(CandidateSearchRecord, candidate.id)

    similar_profiles: set[uuid.UUID] = set()
    if own_index is not None:
        distance = CandidateSearchRecord.embedding.cosine_distance(own_index.embedding)
        similar_profiles = set(
            db.scalars(
                select(CandidateSearchRecord.candidate_id).where(
                    CandidateSearchRecord.candidate_id != candidate.id, distance <= 1 - PROFILE_SIMILARITY
                )
            )
        )

    duplicates = []
    for other in db.scalars(select(CandidateRecord).where(CandidateRecord.id != candidate.id)):
        other_profile = CandidateProfile.model_validate(other.profile)
        reasons = []
        if email and email == _email_key(other_profile.identity.email):
            reasons.append("same email")
        if phone and phone == _phone_key(other_profile.identity.phone):
            reasons.append("same phone number")
        other_name = normalize_text(other_profile.identity.full_name or "")
        if (
            name
            and other_name
            and fuzz.token_sort_ratio(name, other_name) >= NAME_MATCH
            and other.id in similar_profiles
        ):
            reasons.append("similar name and near-identical professional profile")
        if reasons:
            duplicates.append(DuplicateCandidate(other.id, reasons))
    return duplicates


class MergeConflict(ValueError):
    pass


def merge_candidates(db: Session, keep: CandidateRecord, duplicate: CandidateRecord, *, actor: str) -> CandidateRecord:
    """Move the duplicate's applications and match history to `keep`, then delete the duplicate.

    `keep`'s profile is unchanged (the recruiter picks which record to keep). When both are in the same job's
    pipeline, the duplicate's application is dropped and `keep`'s is kept.
    """
    if keep.id == duplicate.id:
        raise MergeConflict("cannot merge a candidate with itself")
    kept_jobs = set(db.scalars(select(ApplicationRecord.job_id).where(ApplicationRecord.candidate_id == keep.id)))
    moved = dropped = 0
    for application in db.scalars(select(ApplicationRecord).where(ApplicationRecord.candidate_id == duplicate.id)):
        if application.job_id in kept_jobs:
            db.delete(application)
            dropped += 1
        else:
            application.candidate_id = keep.id
            moved += 1
    db.execute(update(MatchRecord).where(MatchRecord.candidate_id == duplicate.id).values(candidate_id=keep.id))

    meta = dict(keep.extraction_meta)
    merged = meta.get("merged_documents", [])
    if duplicate.source_document_id is not None:
        merged = [*merged, str(duplicate.source_document_id)]
    meta["merged_documents"] = merged
    keep.extraction_meta = meta
    db.add(
        AuditLogRecord(
            actor=actor,
            action="candidate.merged",
            entity_type="candidate",
            entity_id=keep.id,
            details={"merged_id": str(duplicate.id), "applications_moved": moved, "applications_dropped": dropped},
        )
    )
    db.flush()
    db.delete(duplicate)
    db.commit()
    return keep
