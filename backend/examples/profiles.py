"""Examples for validating extraction output and handing profiles to matching."""

from app.models import CandidateProfile, JobProfile

candidate_payload = {
    "identity": {
        "full_name": "Samira Ben Ali",
        "email": "samira@example.com",
        "location": {"city": "Tunis", "country": "Tunisia", "raw": "Tunis, Tunisia"},
        "linkedin_url": "https://www.linkedin.com/in/samira-ben-ali",
    },
    "professional_title": "Data Engineer",
    "professional_summary": "Data engineer focused on reliable analytics platforms.",
    "seniority": "mid",
    "total_years_experience": 4,
    "domains": ["data engineering", "fintech"],
    "skills": [
        {
            "name": "Python",
            "category": "programming_language",
            "level": "advanced",
            "evidence": "Built ETL services",
            "confidence": 0.95,
        },
        {"name": "PostgreSQL", "category": "database", "years_experience": 3},
        {"name": "Azure", "category": "cloud"},
    ],
    "experiences": [
        {
            "company": "North Africa Finance",
            "job_title": "Data Engineer",
            "dates": {"start_date": "2022-03-01"},
            "current": True,
            "responsibilities": ["Designed batch and streaming pipelines"],
            "achievements": ["Reduced pipeline failures by 30%"],
            "skills_used": [{"name": "Python"}, {"name": "SQL"}],
            "domains": ["fintech"],
        }
    ],
    "languages": [{"language": "French", "level": "C2"}, {"language": "English", "level": "C1"}],
    "source_language": "en",
    "source_type": "cv",
}

job_payload = {
    "title": "Data Engineer",
    "company": "Example Analytics",
    "department_or_team": "Platform Engineering",
    "contract_type": "permanent",
    "schedule": "full_time",
    "seniority": "mid",
    "location": {"city": "Tunis", "country": "Tunisia"},
    "work_mode": "hybrid",
    "experience": {"minimum_years": 3, "relevant_domains": ["data engineering"], "required_seniority": "mid"},
    "skill_requirements": [
        {"name": "Python", "category": "programming_language", "requirement": "required"},
        {"name": "SQL", "category": "database", "requirement": "required"},
        {"name": "Spark", "category": "framework", "requirement": "preferred"},
    ],
    "language_requirements": [{"language": "English", "requirement": "required", "level": "B2"}],
    "responsibilities": ["Build and operate dependable data pipelines"],
    "technical_domains": ["data platforms", "analytics engineering"],
    "compensation": {"minimum": 3000, "maximum": 4500, "currency": "TND", "period": "month"},
    "benefits": ["Professional development budget"],
    "source_language": "en",
}


# This is the same boundary an extraction service would use after receiving LLM JSON.
candidate = CandidateProfile.model_validate(candidate_payload)
job = JobProfile.model_validate(job_payload)


def send_to_matching_service(candidate_profile: CandidateProfile, job_profile: JobProfile) -> dict[str, object]:
    """Example adapter boundary; scoring remains outside the Pydantic models."""
    return {
        "candidate": candidate_profile,
        "job": job_profile,
        "candidate_json": candidate_profile.model_dump(mode="json"),
        "job_json": job_profile.model_dump(mode="json"),
    }
