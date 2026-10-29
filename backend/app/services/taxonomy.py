"""Persist and load the skills taxonomy."""

from __future__ import annotations

import logging

from sqlalchemy import delete, insert, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.db import TaxonomyBroaderRecord, TaxonomySkillRecord, get_engine
from app.matching.taxonomy import Taxonomy, TaxonomySkill, set_taxonomy, taxonomy_rows

logger = logging.getLogger(__name__)
BATCH = 2000


def save_taxonomy(db: Session, taxonomy: Taxonomy) -> None:
    """Replace the stored taxonomy."""
    db.execute(delete(TaxonomyBroaderRecord))
    db.execute(delete(TaxonomySkillRecord))
    rows = [{**row, "version": taxonomy.version} for row in taxonomy_rows(taxonomy)]
    for start in range(0, len(rows), BATCH):
        db.execute(insert(TaxonomySkillRecord), rows[start : start + BATCH])
    relations = [{"narrower_uri": n, "broader_uri": b} for n, wider in taxonomy.broader.items() for b in wider]
    for start in range(0, len(relations), BATCH):
        db.execute(insert(TaxonomyBroaderRecord), relations[start : start + BATCH])
    db.commit()


def load_taxonomy(db: Session) -> Taxonomy | None:
    records = list(db.scalars(select(TaxonomySkillRecord)))
    if not records:
        return None
    skills = {
        r.uri: TaxonomySkill(
            uri=r.uri,
            labels={lang: label for lang, label in (("en", r.label_en), ("fr", r.label_fr)) if label},
            alt_labels=list(r.alt_labels),
            skill_type=r.skill_type,
        )
        for r in records
    }
    broader: dict[str, set[str]] = {}
    for relation in db.scalars(select(TaxonomyBroaderRecord)):
        broader.setdefault(relation.narrower_uri, set()).add(relation.broader_uri)
    return Taxonomy(version=records[0].version, skills=skills, broader=broader)


def activate_stored_taxonomy() -> None:
    """Load the stored taxonomy at startup; the curated graph alone is used when none is stored or the DB is down."""
    try:
        with Session(get_engine()) as db:
            taxonomy = load_taxonomy(db)
    except (OperationalError, ProgrammingError) as exc:
        logger.warning("taxonomy not loaded: %s", exc.__class__.__name__)
        return
    set_taxonomy(taxonomy)
    if taxonomy:
        logger.info("taxonomy %s loaded (%d skills)", taxonomy.version, len(taxonomy.skills))
