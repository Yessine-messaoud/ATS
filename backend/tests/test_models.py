from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.models import (
    SCHEMA_VERSION,
    CandidateIdentity,
    CandidateProfile,
    Compensation,
    DateRange,
    Experience,
    JobProfile,
    LanguageLevel,
    RequirementKind,
    Skill,
    SkillCategory,
    SkillRequirement,
)


def test_candidate_accepts_nested_profile_and_missing_optional_fields() -> None:
    profile = CandidateProfile.model_validate(
        {
            "identity": {"full_name": "Ada Lovelace", "email": "ada@example.com"},
            "skills": [{"name": "Python", "category": "programming_language", "years_experience": 4}],
            "experiences": [
                {
                    "company": "Analytical Engines",
                    "job_title": "Data Engineer",
                    "current": True,
                    "responsibilities": ["Built data pipelines"],
                }
            ],
        }
    )

    assert profile.schema_version == SCHEMA_VERSION
    assert profile.identity.full_name == "Ada Lovelace"
    assert profile.identity.phone is None
    assert profile.skills[0].category is SkillCategory.PROGRAMMING_LANGUAGE
    assert profile.experiences[0].skills_used == []
    assert profile.experiences[0].current is True


def test_job_distinguishes_required_and_preferred_skills() -> None:
    job = JobProfile.model_validate(
        {
            "title": "Data Engineer",
            "skill_requirements": [
                {"name": "Python", "requirement": "required"},
                {"name": "Spark", "requirement": "preferred", "minimum_years": 1},
            ],
        }
    )

    assert job.skill_requirements[0].requirement is RequirementKind.REQUIRED
    assert job.skill_requirements[1].requirement is RequirementKind.PREFERRED
    assert job.skill_requirements[1].minimum_years == 1


def test_language_levels_are_shared_cefr_on_both_sides() -> None:
    candidate = CandidateProfile.model_validate({"languages": [{"language": "English", "level": "C1"}]})
    job = JobProfile.model_validate(
        {"title": "x", "language_requirements": [{"language": "English", "requirement": "required", "level": "B2"}]}
    )

    assert candidate.languages[0].level is LanguageLevel.C1
    assert job.language_requirements[0].level is LanguageLevel.B2


def test_extracted_items_carry_evidence_fields() -> None:
    skill = Skill(name="Python", evidence="Built ETL services in Python", confidence=0.9)

    assert skill.verified is None
    with pytest.raises(ValidationError):
        Skill(name="Python", confidence=1.5)


def test_date_ranges_reject_reversed_dates() -> None:
    with pytest.raises(ValidationError, match="end_date"):
        DateRange(start_date=date(2025, 1, 1), end_date=date(2024, 12, 31))


def test_current_experience_cannot_have_end_date() -> None:
    with pytest.raises(ValidationError, match="current experience"):
        Experience.model_validate(
            {
                "company": "Example",
                "job_title": "Engineer",
                "current": True,
                "dates": {"start_date": "2024-01-01", "end_date": "2025-01-01"},
            }
        )


def test_duration_must_match_dates_within_tolerance() -> None:
    dates = {"start_date": "2024-01-01", "end_date": "2025-01-01"}

    assert Experience.model_validate({"company": "a", "job_title": "b", "dates": dates, "duration_months": 13})
    with pytest.raises(ValidationError, match="contradicts dates"):
        Experience.model_validate({"company": "a", "job_title": "b", "dates": dates, "duration_months": 60})


def test_salary_range_rejects_maximum_below_minimum() -> None:
    with pytest.raises(ValidationError, match="maximum compensation"):
        Compensation(minimum=Decimal("90000"), maximum=Decimal("80000"), currency="USD")


def test_currency_is_normalized_iso_4217() -> None:
    assert Compensation.model_validate({"currency": "tnd"}).currency == "TND"
    with pytest.raises(ValidationError):
        Compensation.model_validate({"currency": "abc"})


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (CandidateProfile, {"total_years_experience": float("inf")}),
        (CandidateProfile, {"total_years_experience": float("nan")}),
        (CandidateProfile, {"total_years_experience": -1}),
        (Skill, {"name": ""}),
        (Skill, {"name": "   "}),
        (Skill, {"name": "Python", "level": "native"}),
        (CandidateIdentity, {"linkedin_url": "not a url"}),
        (CandidateIdentity, {"github_url": "ftp://example.com/x"}),
        (CandidateIdentity, {"email": "not-an-email"}),
        (SkillRequirement, {"name": "Python", "requirement": "unknown"}),
        (
            JobProfile,
            {"title": "x", "language_requirements": [{"language": "French", "requirement": "required", "level": "ok"}]},
        ),
        (JobProfile, {"title": ""}),
        (CandidateProfile, {"nickname": "unexpected LLM field"}),
    ],
)
def test_invalid_data_is_rejected(model: Any, payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_scheme_less_urls_become_https() -> None:
    identity = CandidateIdentity.model_validate(
        {"linkedin_url": "linkedin.com/in/samira", "github_url": "github.com/s"}
    )
    assert identity.linkedin_url == "https://linkedin.com/in/samira"
    assert identity.github_url == "https://github.com/s"


def test_examples_validate() -> None:
    from examples.profiles import candidate, job, send_to_matching_service

    result = send_to_matching_service(candidate, job)

    assert result["candidate_json"]["skills"][0]["name"] == "Python"  # type: ignore[index]
    assert job.compensation is not None and job.compensation.currency == "TND"


def test_json_schema_is_generated_for_llm_structured_output() -> None:
    schema = CandidateProfile.model_json_schema()

    assert "raw_text" not in schema["properties"]
    assert schema["additionalProperties"] is False
