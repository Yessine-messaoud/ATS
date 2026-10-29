from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import (
    CandidateProfile,
    Compensation,
    DateRange,
    Experience,
    JobProfile,
    RequirementKind,
    SkillRequirement,
)


def test_candidate_accepts_nested_profile_and_missing_optional_fields() -> None:
    profile = CandidateProfile.model_validate(
        {
            "identity": {"full_name": "Ada Lovelace", "email": "ada@example.com"},
            "programming_languages": [{"name": "Python", "years_experience": 4}],
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

    assert profile.identity.full_name == "Ada Lovelace"
    assert profile.identity.phone is None
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


def test_date_ranges_reject_reversed_dates() -> None:
    with pytest.raises(ValidationError, match="end_date"):
        DateRange(start_date=date(2025, 1, 1), end_date=date(2024, 12, 31))


def test_current_experience_cannot_have_end_date() -> None:
    with pytest.raises(ValidationError, match="current experience"):
        Experience(
            company="Example",
            job_title="Engineer",
            current=True,
            dates={"start_date": "2024-01-01", "end_date": "2025-01-01"},
        )


def test_salary_range_rejects_maximum_below_minimum() -> None:
    with pytest.raises(ValidationError, match="maximum compensation"):
        Compensation(minimum=Decimal("90000"), maximum=Decimal("80000"), currency="USD")


def test_invalid_data_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CandidateProfile.model_validate(
            {"identity": {"email": "not-an-email"}, "total_years_experience": -1}
        )

    with pytest.raises(ValidationError):
        SkillRequirement(name="Python", requirement="unknown")
