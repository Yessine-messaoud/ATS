"""Counterfactual fairness suite: attributes that must never change a score, a ranking or a knock-out.

Each test swaps one attribute (name, contact details, gendered wording, protected-characteristic mentions) on an
otherwise identical candidate and requires the complete match result, not only the overall score, to be equal.
"""

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from app.extraction.prompts import CV_SYSTEM_PROMPT
from app.models import CandidateProfile
from tests.test_matching import CANDIDATE, JOB, run, with_

NAMES = [
    ("Samira Ben Ali", "samira.benali@example.com"),
    ("Mohamed Trabelsi", "m.trabelsi@example.tn"),
    ("Claire Dubois", "claire.dubois@example.fr"),
    ("Ngozi Okafor", "ngozi.okafor@example.ng"),
    ("Wei Zhang", "wei.zhang@example.cn"),
    ("Jean-Baptiste Martin", "jb.martin@example.fr"),
    ("Fatma Gharbi", "fatma.gharbi@example.tn"),
    ("Priya Natarajan", "priya.n@example.in"),
]

GENDERED_TITLES = [
    ("Ingénieur de données", "Ingénieure de données"),
    ("Développeur Python", "Développeuse Python"),
    ("Consultant data", "Consultante data"),
    ("Chef de projet data", "Cheffe de projet data"),
    ("Directeur technique", "Directrice technique"),
]

PROTECTED_FIELDS = {
    "gender",
    "sex",
    "age",
    "date_of_birth",
    "birth_date",
    "nationality",
    "marital_status",
    "religion",
    "photo",
    "ethnicity",
    "disability",
    "pregnancy",
}


def result(candidate: dict[str, Any], job: dict[str, Any] = JOB) -> dict[str, Any]:
    dumped: dict[str, Any] = run(candidate, job).model_dump()
    return dumped


def with_experience_title(candidate: dict[str, Any], title: str) -> dict[str, Any]:
    experiences = copy.deepcopy(candidate["experiences"])
    experiences[0]["job_title"] = title
    return with_(candidate, experiences=experiences, professional_title=title)


@pytest.mark.parametrize(("name", "email"), NAMES)
def test_name_and_contact_details_do_not_change_the_result(name: str, email: str) -> None:
    identity = {
        **CANDIDATE["identity"],
        "full_name": name,
        "email": email,
        "phone": "+1 555 0100",
        "linkedin_url": None,
    }
    assert result(with_(CANDIDATE, identity=identity)) == result(CANDIDATE)


@pytest.mark.parametrize(("masculine", "feminine"), GENDERED_TITLES)
def test_gendered_job_titles_score_the_same(masculine: str, feminine: str) -> None:
    job = with_(JOB, title=masculine)
    assert result(with_experience_title(CANDIDATE, feminine), job) == result(
        with_experience_title(CANDIDATE, masculine), job
    )


@pytest.mark.parametrize(
    "mention",
    [
        "Mother of two children.",
        "Married, 45 years old.",
        "Muslim, practising.",
        "Wheelchair user.",
        "Nationalité : tunisienne.",
        "Née le 12/03/1980.",
    ],
)
def test_protected_characteristics_in_free_text_do_not_change_the_result(mention: str) -> None:
    summary = "Data engineer building batch and streaming pipelines."
    baseline = with_(CANDIDATE, professional_summary=summary)
    mentioned = with_(
        CANDIDATE,
        professional_summary=f"{summary} {mention}",
        professionally_relevant_interests=[mention],
    )
    assert result(mentioned) == result(baseline)


def test_the_profile_schema_has_no_protected_attributes() -> None:
    """The extraction schema is the only input to scoring; these fields cannot reach it."""

    def keys(schema: Any) -> set[str]:
        if isinstance(schema, dict):
            found = set(schema.get("properties", {}))
            for value in schema.values():
                found |= keys(value)
            return found
        if isinstance(schema, list):
            return set().union(*(keys(item) for item in schema)) if schema else set()
        return set()

    assert keys(CandidateProfile.model_json_schema()) & PROTECTED_FIELDS == set()
    with pytest.raises(ValidationError):
        CandidateProfile.model_validate({**CANDIDATE, "gender": "female"})


def test_the_extraction_prompt_forbids_protected_characteristics() -> None:
    prompt = CV_SYSTEM_PROMPT.lower()
    for word in ("gender", "age", "nationality", "photo"):
        assert word in prompt


def test_ranking_order_is_invariant_to_names() -> None:
    """Swapping names between candidates swaps nothing else: each profile keeps its score."""
    weaker = copy.deepcopy(CANDIDATE)
    weaker["skills"] = [{"name": "Python"}]
    weaker["experiences"][0]["responsibilities"] = ["Maintained Python scripts"]
    strong_a = with_(CANDIDATE, identity={**CANDIDATE["identity"], "full_name": "Claire Dubois"})
    weak_a = with_(weaker, identity={**CANDIDATE["identity"], "full_name": "Mohamed Trabelsi"})
    strong_b = with_(CANDIDATE, identity={**CANDIDATE["identity"], "full_name": "Mohamed Trabelsi"})
    weak_b = with_(weaker, identity={**CANDIDATE["identity"], "full_name": "Claire Dubois"})

    scores_a = [run(c).overall_score for c in (strong_a, weak_a)]
    scores_b = [run(c).overall_score for c in (strong_b, weak_b)]
    assert scores_a == scores_b
    assert scores_a[0] > scores_a[1]


# --- protected characteristics copied by the model ------------------------------------------------------------------


def test_protected_characteristics_are_removed_after_extraction() -> None:
    from app.extraction.protected import scrub_protected

    data = {
        "identity": {"full_name": "Christian Marié"},
        "professional_summary": "Ingénieur DevOps, 10 ans d'expérience. Né le 03/07/1992 — Célibataire",
        "professionally_relevant_interests": ["Football", "Mother of two children", "Religion : musulmane"],
        "experiences": [
            {"company": "Acme", "job_title": "SRE", "evidence": "SRE chez Acme | Nationalité : tunisienne"}
        ],
    }
    cleaned, removed = scrub_protected(data)

    assert cleaned["identity"] == {"full_name": "Christian Marié"}
    assert cleaned["professional_summary"] == "Ingénieur DevOps, 10 ans d'expérience"
    assert cleaned["professionally_relevant_interests"] == ["Football"]
    assert cleaned["experiences"][0]["evidence"] == "SRE chez Acme"
    assert len(removed) == 5


def test_extraction_reports_removed_protected_characteristics() -> None:
    from app.extraction import CANDIDATE_TARGET, extract
    from tests.conftest import FakeLLM

    text = "Samira Ben Ali\nData engineer. Née le 03/07/1992, mariée\nPython"
    response = {"identity": {"full_name": "Samira Ben Ali"}, "professional_summary": "Data engineer. Mariée"}
    result = extract(FakeLLM([response]), CANDIDATE_TARGET, text, max_repairs=0)

    assert result.profile.professional_summary == "Data engineer"
    assert result.meta["protected_attributes_removed"] == 1
