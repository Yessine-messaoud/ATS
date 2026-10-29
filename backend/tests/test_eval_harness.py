"""The eval harness itself must be correct: test the scoring, the data set and the offline pipeline."""

import json
from pathlib import Path

from app.config import Settings
from app.ingestion import DocumentFlag, ingest_document
from app.models import CandidateProfile
from eval.metrics import score_candidate, score_sets
from eval.render import render_pdf

DATA = Path(__file__).parents[1] / "eval" / "data"


def test_set_scoring_uses_aliases_and_fuzzy_matching() -> None:
    score = score_sets(
        ["Spark", "Postgres", "scikit learn", "SQL Server"], ["Apache Spark", "PostgreSQL", "scikit-learn", "SQL"]
    )

    assert (score.tp, score.fp, score.fn) == (3, 1, 1)
    assert score.false_positives == ["SQL Server"]  # a different skill, not a fuzzy match
    assert score.false_negatives == ["SQL"]
    assert round(score.f1, 2) == 0.75


def test_candidate_scoring_detects_sensitive_leaks_and_language_levels() -> None:
    gold = json.loads((DATA / "cvs" / "en-02-ml-engineer.gold.json").read_text(encoding="utf-8"))
    profile = CandidateProfile.model_validate(
        {
            "identity": {"full_name": "Youssef Trabelsi", "email": "youssef.trabelsi@example.com"},
            "professional_summary": "Born in 1995.",
            "languages": [{"language": "Arabic", "level": "native"}, {"language": "French", "level": "C1"}],
        }
    )

    scores = score_candidate(profile, gold)

    assert scores["sensitive_leaks"] == ["1995"]
    assert scores["scalars"] == {"full_name": True, "email": True}
    assert scores["languages"].tp == 1  # Arabic; French has the wrong level and English is missing
    assert scores["languages"].fn == 2


def test_every_case_has_a_valid_gold_file() -> None:
    for kind, required in [("cvs", {"skills", "experiences", "languages"}), ("jobs", {"required_skills"})]:
        texts = sorted((DATA / kind).glob("*.txt"))
        assert texts, kind
        for text_file in texts:
            gold = json.loads(text_file.with_suffix(".gold.json").read_text(encoding="utf-8"))
            assert required <= gold.keys(), text_file.name


def test_rendered_cvs_round_trip_through_ingestion() -> None:
    settings = Settings()
    for text_file in sorted((DATA / "cvs").glob("*.txt")):
        gold = json.loads(text_file.with_suffix(".gold.json").read_text(encoding="utf-8"))
        document = ingest_document(
            render_pdf(text_file.read_text(encoding="utf-8"), hidden_lines=gold.get("hidden_text")), settings
        )

        assert gold["email"] in document.text, text_file.name
        for expected in gold.get("expect_flags", []):
            assert DocumentFlag(expected) in document.flags, text_file.name
        for hidden in gold.get("hidden_text", []):
            assert hidden[:30] not in document.text, text_file.name
