from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.matching import FactorStatus, KnockoutStatus, ScoringWeights, match
from app.matching.features import relevant_experience_months, skill_index, skill_strength
from app.matching.skills import canonical, mention_pattern, skill_credit
from app.models import CandidateProfile, JobProfile

TODAY = date(2026, 10, 29)

JOB: dict[str, Any] = {
    "title": "Data Engineer",
    "location": {"city": "Tunis", "country": "Tunisia"},
    "work_mode": "hybrid",
    "experience": {"minimum_years": 3},
    "skill_requirements": [
        {"name": "Python", "requirement": "required"},
        {"name": "SQL", "requirement": "required"},
        {"name": "Spark", "requirement": "required"},
        {"name": "Kafka", "requirement": "preferred"},
    ],
    "language_requirements": [{"language": "English", "requirement": "required", "level": "B2"}],
}

CANDIDATE: dict[str, Any] = {
    "identity": {
        "full_name": "Samira Ben Ali",
        "email": "samira@example.com",
        "phone": "+216 20 000 000",
        "linkedin_url": "https://www.linkedin.com/in/samira",
        "location": {"city": "Tunis", "country": "Tunisia"},
    },
    "skills": [{"name": "Python"}, {"name": "PostgreSQL"}, {"name": "Apache Spark"}],
    "experiences": [
        {
            "company": "North Africa Finance",
            "job_title": "Data Engineer",
            "dates": {"start_date": "2022-03-01"},
            "current": True,
            "responsibilities": ["Built Spark pipelines in Python on PostgreSQL"],
        }
    ],
    "languages": [{"language": "Anglais", "level": "C1"}],
}


def run(candidate: dict[str, Any] = CANDIDATE, job: dict[str, Any] = JOB, **kwargs: Any) -> Any:
    return match(CandidateProfile.model_validate(candidate), JobProfile.model_validate(job), today=TODAY, **kwargs)


def with_(base: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {**base, **changes}


# --- skills graph -------------------------------------------------------------------------------------------------


def test_synonyms_and_canonical_names() -> None:
    assert canonical("  PySpark ") == "apache spark"
    assert canonical("Node") == "node.js"
    assert canonical("Vision par ordinateur") == "computer vision"


@pytest.mark.parametrize(
    ("have", "want", "credit", "how"),
    [
        ("postgresql", "sql", 0.9, "implied"),
        ("express", "javascript", 0.9, "implied"),  # transitive: express -> node.js -> javascript
        ("mysql", "postgresql", 0.7, "related"),
        ("sql server", "sql", 0.9, "implied"),
        ("sql", "sql server", 0.0, "none"),  # knowing SQL does not prove SQL Server
        ("java", "javascript", 0.0, "none"),
    ],
)
def test_skill_credit(have: str, want: str, credit: float, how: str) -> None:
    assert skill_credit(have, want) == (credit, how)


def test_mentions_match_whole_words_including_symbols() -> None:
    assert mention_pattern("c++").search("built a c++ engine")
    assert not mention_pattern("c").search("built a c++ engine")
    assert mention_pattern("node.js").search("apis in node.js and express")
    assert not mention_pattern("java").search("javascript only")


# --- features ------------------------------------------------------------------------------------------------------


def test_professional_use_beats_projects_beats_a_bare_listing() -> None:
    profile = CandidateProfile.model_validate(
        {
            "skills": [{"name": "Python"}, {"name": "Go"}],
            "projects": [{"name": "p", "technologies": [{"name": "Rust"}]}],
            "experiences": [CANDIDATE["experiences"][0]],
        }
    )
    index = skill_index(profile, TODAY)

    used, project, listed = (skill_strength(index[k], TODAY) for k in ("python", "rust", "go"))
    assert used > project > listed > 0


def test_unverified_skill_earns_no_credit() -> None:
    profile = CandidateProfile.model_validate(
        {"skills": [{"name": "Kubernetes", "evidence": "hidden text", "verified": False}]}
    )

    assert skill_strength(skill_index(profile, TODAY)["kubernetes"], TODAY) == 0


def test_overlapping_positions_are_not_double_counted_and_internships_count_half() -> None:
    profile = CandidateProfile.model_validate(
        {
            "experiences": [
                {
                    "company": "A",
                    "job_title": "Engineer",
                    "dates": {"start_date": "2020-01-01", "end_date": "2022-01-01"},
                },
                {
                    "company": "B",
                    "job_title": "Freelance",
                    "dates": {"start_date": "2021-01-01", "end_date": "2022-01-01"},
                },
                {
                    "company": "C",
                    "job_title": "Intern",
                    "dates": {"start_date": "2019-01-01", "end_date": "2019-07-01"},
                },
            ]
        }
    )

    months, positions = relevant_experience_months(profile, TODAY, relevant=None)

    assert positions == 3
    assert round(months) == 24 + 3


# --- knock-outs ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("languages", "status"),
    [
        ([{"language": "English", "level": "C1"}], KnockoutStatus.PASS),
        ([{"language": "English", "level": "B1"}], KnockoutStatus.FAIL),
        ([{"language": "English"}], KnockoutStatus.UNKNOWN),
        ([{"language": "French", "level": "C2"}], KnockoutStatus.FAIL),
    ],
)
def test_required_language_knockout(languages: list[dict[str, str]], status: KnockoutStatus) -> None:
    result = run(with_(CANDIDATE, languages=languages))

    assert result.knockouts[0].status is status
    assert result.passed_knockouts is (status is not KnockoutStatus.FAIL)


def test_location_knockout_respects_relocation() -> None:
    abroad = {**CANDIDATE["identity"], "location": {"city": "Paris", "country": "France"}}

    assert run(with_(CANDIDATE, identity=abroad)).knockouts[-1].status is KnockoutStatus.UNKNOWN
    relocating = with_(CANDIDATE, identity=abroad, work_preferences={"willing_to_relocate": True})
    assert run(relocating).knockouts[-1].status is KnockoutStatus.PASS
    staying = with_(CANDIDATE, identity=abroad, work_preferences={"willing_to_relocate": False})
    assert run(staying).knockouts[-1].status is KnockoutStatus.FAIL


def test_required_certification_knockout() -> None:
    job = with_(JOB, certification_requirements=[{"name": "AWS Solutions Architect", "requirement": "required"}])

    assert run(job=job).knockouts[1].status is KnockoutStatus.FAIL
    certified = with_(CANDIDATE, certifications=[{"name": "AWS Certified Solutions Architect - Associate"}])
    assert run(certified, job).knockouts[1].status is KnockoutStatus.PASS


def test_knocked_out_candidates_are_still_scored() -> None:
    result = run(with_(CANDIDATE, languages=[]))

    assert not result.passed_knockouts
    assert result.overall_score > 50


# --- engine ----------------------------------------------------------------------------------------------------------


def test_strong_candidate_scores_high_with_traceable_factors() -> None:
    result = run()

    # Below 100 mainly because the preferred skill (Kafka) is missing.
    assert result.overall_score > 75
    assert result.missing_required == []
    skills = next(d for d in result.dimensions if d.name == "required_skills")
    sql = next(f for f in skills.factors if f.id == "skill:sql")
    assert sql.status is FactorStatus.MET
    assert "via PostgreSQL" in sql.detail
    spark = next(f for f in skills.factors if f.id == "skill:apache spark")
    assert "used for" in spark.detail  # "Built Spark pipelines" counts as use of "Apache Spark"
    assert round(sum(d.weight for d in result.dimensions), 3) == 1


def test_missing_required_skill_applies_a_visible_penalty() -> None:
    without_spark = with_(
        CANDIDATE,
        skills=[{"name": "Python"}, {"name": "PostgreSQL"}],
        experiences=[{**CANDIDATE["experiences"][0], "responsibilities": ["Built pipelines in Python on PostgreSQL"]}],
    )

    result = run(without_spark)

    assert result.missing_required == ["Spark"]
    assert result.penalty_multiplier == pytest.approx(0.92)
    assert result.overall_score == pytest.approx(result.raw_score * 0.92, abs=0.1)


def test_dimensions_without_job_criteria_are_excluded_and_weights_renormalized() -> None:
    result = run(job={"title": "x", "skill_requirements": [{"name": "Python", "requirement": "required"}]})

    assert [d.name for d in result.dimensions] == ["required_skills"]
    assert result.dimensions[0].weight == 1


def test_custom_weights_change_the_score() -> None:
    weak_english = with_(CANDIDATE, languages=[{"language": "English", "level": "A2"}])
    default = run(weak_english)
    language_heavy = run(weak_english, weights=ScoringWeights(languages=200))

    assert language_heavy.overall_score < default.overall_score


def test_weights_must_not_all_be_zero() -> None:
    zeros = dict.fromkeys(
        ["required_skills", "preferred_skills", "experience", "seniority", "languages", "education", "location"], 0
    )
    with pytest.raises(ValidationError):
        ScoringWeights(**zeros)


def test_scoring_is_deterministic() -> None:
    assert run().model_dump() == run().model_dump()


def test_identity_does_not_influence_the_score() -> None:
    """Counterfactual fairness: changing name, email, phone and links must not change anything."""
    other_identity = {
        "full_name": "John Smith",
        "email": "john.smith@example.org",
        "phone": "+33 6 00 00 00 00",
        "github_url": "https://github.com/someone",
        "location": CANDIDATE["identity"]["location"],
    }

    assert run(with_(CANDIDATE, identity=other_identity)).model_dump() == run().model_dump()
