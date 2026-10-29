from typing import Any

import pytest

from app.extraction import CANDIDATE_TARGET, JOB_TARGET, ExtractionFailed, extract, tool_spec
from app.extraction.evidence import verify_evidence
from app.extraction.sections import detect_sections
from app.extraction.validation import validate_partially
from app.models import CandidateProfile, JobProfile
from tests.conftest import FakeLLM

CV_TEXT = """Samira Ben Ali
Data Engineer - Tunis

EXPÉRIENCE PROFESSIONNELLE
North Africa Finance - Data Engineer (mars 2022 - présent)
Built ETL services in Python and PostgreSQL; reduced pipeline failures by 30%.

Formation
Université de Tunis - Master en informatique (2021)

Langues
Français : langue maternelle ; Anglais : C1
"""

VALID_CV: dict[str, Any] = {
    "identity": {"full_name": "Samira Ben Ali", "email": "samira@example.com"},
    "skills": [
        {"name": "Python", "category": "programming_language", "evidence": "Built ETL services in Python"},
        {"name": "PostgreSQL", "category": "database", "evidence": "Python and PostgreSQL"},
    ],
    "experiences": [
        {
            "company": "North Africa Finance",
            "job_title": "Data Engineer",
            "dates": {"start_date": "2022-03-01"},
            "current": True,
            "evidence": "North Africa Finance - Data Engineer (mars 2022 - présent)",
        }
    ],
    "education": [{"institution": "Université de Tunis", "degree": "Master en informatique"}],
    "languages": [{"language": "French", "level": "native", "evidence": "Français : langue maternelle"}],
}


def test_sections_are_detected_in_french_and_english() -> None:
    names = [section.name for section in detect_sections(CV_TEXT + "\nSKILLS\nPython\n")]

    assert names == ["experience", "education", "languages", "skills"]


def test_tool_schema_hides_system_fields() -> None:
    schema = tool_spec(CANDIDATE_TARGET).input_schema

    assert "schema_version" not in schema["properties"]
    assert "verified" not in schema["$defs"]["Skill"]["properties"]
    assert "evidence" in schema["$defs"]["Skill"]["properties"]


def test_valid_record_is_accepted_on_first_call() -> None:
    llm = FakeLLM([VALID_CV])

    result = extract(llm, CANDIDATE_TARGET, CV_TEXT, max_repairs=2)

    assert result.profile.identity.full_name == "Samira Ben Ali"
    assert result.meta["llm_calls"] == 1
    assert result.meta["prompt_version"] == "cv-v1"
    assert result.issues == []
    assert "<document" in llm.sessions[0].prompts[0]


def test_invalid_record_is_corrected_through_feedback() -> None:
    invalid = {**VALID_CV, "total_years_experience": -3}
    llm = FakeLLM([invalid, VALID_CV])

    result = extract(llm, CANDIDATE_TARGET, CV_TEXT, max_repairs=2)

    assert result.meta["llm_calls"] == 2
    assert "total_years_experience" in llm.sessions[0].prompts[1]
    assert result.profile.total_years_experience is None


def test_missing_tool_call_is_requested_again() -> None:
    llm = FakeLLM([None, VALID_CV])

    result = extract(llm, CANDIDATE_TARGET, CV_TEXT, max_repairs=1)

    assert "did not call the tool" in llm.sessions[0].prompts[1]
    assert result.profile.experiences[0].company == "North Africa Finance"


def test_partial_validation_keeps_valid_data_after_repairs_are_exhausted() -> None:
    broken = {
        **VALID_CV,
        "identity": {"full_name": "Samira Ben Ali", "email": "samira at example"},
        "experiences": [*VALID_CV["experiences"], {"job_title": "Intern"}],
    }
    llm = FakeLLM([broken, broken])

    result = extract(llm, CANDIDATE_TARGET, CV_TEXT, max_repairs=1)

    assert result.profile.identity.full_name == "Samira Ben Ali"
    assert result.profile.identity.email is None
    assert len(result.profile.experiences) == 1
    assert {issue.path for issue in result.issues} == {"identity.email", "experiences.1"}


def test_unrecoverable_record_fails() -> None:
    llm = FakeLLM([{"title": ""}])

    with pytest.raises(ExtractionFailed):
        extract(llm, JOB_TARGET, "We are hiring a data engineer in Tunis with Python.", max_repairs=0)


def test_partial_validation_drops_items_rejected_by_object_validators() -> None:
    payload = {
        "experiences": [
            {"company": "A", "job_title": "B", "current": True, "dates": {"end_date": "2024-01-01"}},
            {"company": "C", "job_title": "D"},
        ]
    }

    profile, issues = validate_partially(CandidateProfile, payload)

    assert profile is not None
    assert [e.company for e in profile.experiences] == ["C"]
    assert issues[0].action == "dropped item"


def test_evidence_is_verified_against_source_text() -> None:
    profile = CandidateProfile.model_validate(
        {
            **VALID_CV,
            "skills": [
                *VALID_CV["skills"],
                {"name": "Kubernetes", "evidence": "Deployed Kubernetes clusters at scale"},
                {"name": "Spark"},
            ],
        }
    )

    stats = verify_evidence(profile, CV_TEXT)

    verified = {skill.name: skill.verified for skill in profile.skills}
    assert verified == {"Python": True, "PostgreSQL": True, "Kubernetes": False, "Spark": False}
    assert profile.experiences[0].verified is True
    assert profile.education[0].verified is True  # no quote: falls back to the institution name
    assert stats.unverified == 2
    assert stats.unverified_paths == ["skills[2]", "skills[3]"]


def test_evidence_matching_tolerates_accents_case_and_spacing() -> None:
    profile = JobProfile.model_validate(
        {
            "title": "x",
            "skill_requirements": [{"name": "SQL", "requirement": "required", "evidence": "maitrise  du SQL"}],
        }
    )

    verify_evidence(profile, "Profil recherché : Maîtrise du SQL et de Python.")

    assert profile.skill_requirements[0].verified is True
