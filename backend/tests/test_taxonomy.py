"""ESCO import and taxonomy-aware normalization, using a tiny fixture in the ESCO CSV layout (fake URIs)."""

import csv
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.matching import engine_version
from app.matching.skills import canonical, implied_by, skill_credit
from app.matching.taxonomy import Taxonomy, read_esco_csv, set_taxonomy
from app.services.taxonomy import load_taxonomy, save_taxonomy
from tests.test_matching import run

DBMS, POSTGRES, SPARK = "urn:test:skill:dbms", "urn:test:skill:postgresql", "urn:test:skill:spark"
SKILL_COLUMNS = ["conceptType", "conceptUri", "skillType", "reuseLevel", "preferredLabel", "altLabels", "description"]


def write(path: Path, columns: list[str], rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def esco_files(tmp_path: Path) -> tuple[dict[str, Path], Path]:
    def skill(uri: str, label: str, alt: str = "") -> dict[str, str]:
        return {
            "conceptType": "KnowledgeSkillCompetence",
            "conceptUri": uri,
            "skillType": "knowledge",
            "preferredLabel": label,
            "altLabels": alt,
        }

    en = write(
        tmp_path / "skills_en.csv",
        SKILL_COLUMNS,
        [
            skill(DBMS, "database management systems", "DBMS\nrelational database management"),
            skill(POSTGRES, "PostgreSQL"),
            skill(SPARK, "Apache Spark", "spark big data framework"),
        ],
    )
    fr = write(
        tmp_path / "skills_fr.csv",
        SKILL_COLUMNS,
        [skill(DBMS, "systèmes de gestion de bases de données", "SGBD"), skill(SPARK, "Apache Spark")],
    )
    broader = write(
        tmp_path / "broaderRelationsSkillPillar.csv",
        ["conceptType", "conceptUri", "broaderType", "broaderUri"],
        [
            {
                "conceptType": "KnowledgeSkillCompetence",
                "conceptUri": POSTGRES,
                "broaderType": "KnowledgeSkillCompetence",
                "broaderUri": DBMS,
            }
        ],
    )
    return {"en": en, "fr": fr}, broader


@pytest.fixture
def taxonomy(esco_files: tuple[dict[str, Path], Path]) -> Iterator[Taxonomy]:
    loaded = read_esco_csv(*esco_files, version="esco-test")
    set_taxonomy(loaded)
    yield loaded
    set_taxonomy(None)


def test_csv_import_reads_languages_alt_labels_and_relations(esco_files: tuple[dict[str, Path], Path]) -> None:
    loaded = read_esco_csv(*esco_files, version="esco-test")

    assert loaded.skills[DBMS].labels == {
        "en": "database management systems",
        "fr": "systèmes de gestion de bases de données",
    }
    assert {"DBMS", "relational database management", "SGBD"} <= set(loaded.skills[DBMS].alt_labels)
    assert loaded.broader[POSTGRES] == {DBMS}


def test_french_and_alternative_labels_map_to_one_canonical_skill(taxonomy: Taxonomy) -> None:
    assert canonical("SGBD") == canonical("Systèmes de gestion de bases de données") == "database management systems"
    assert canonical("spark big data framework") == "apache spark"
    assert canonical("Rust") == "rust"  # unknown to the taxonomy: unchanged


def test_narrower_skill_implies_broader_concept(taxonomy: Taxonomy) -> None:
    assert "database management systems" in implied_by("postgresql")
    assert "sql" in implied_by("postgresql")  # the curated graph still applies
    assert skill_credit("postgresql", canonical("SGBD")) == (0.9, "implied")


def test_engine_version_records_the_taxonomy(taxonomy: Taxonomy) -> None:
    assert engine_version() == "match-v1+esco-test"
    assert run().engine_version == "match-v1+esco-test"


def test_without_taxonomy_behaviour_is_unchanged() -> None:
    set_taxonomy(None)

    assert canonical("SGBD") == "sgbd"
    assert engine_version() == "match-v1"


def test_taxonomy_round_trips_through_the_database(db: Session, esco_files: tuple[dict[str, Path], Path]) -> None:
    loaded = read_esco_csv(*esco_files, version="esco-test")

    save_taxonomy(db, loaded)
    stored = load_taxonomy(db)

    assert stored is not None
    assert stored.version == "esco-test"
    assert stored.skills.keys() == loaded.skills.keys()
    assert stored.broader == loaded.broader
