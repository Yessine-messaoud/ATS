"""Canonical candidate profile models."""

from __future__ import annotations

from datetime import date

from pydantic import EmailStr, Field, field_validator, model_validator

from .common import (
    Certification,
    ContractType,
    DateRange,
    DomainModel,
    Education,
    Language,
    Location,
    ProficiencyLevel,
    Skill,
    SeniorityLevel,
    WorkMode,
    WorkPreferences,
)


class CandidateIdentity(DomainModel):
    full_name: str | None = Field(default=None, description="Candidate's full name if provided.")
    email: EmailStr | None = Field(default=None, description="Candidate email address.")
    phone: str | None = Field(default=None, description="Phone number as supplied; avoid guessing country codes.")
    location: Location | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None


class Experience(DomainModel):
    company: str = Field(description="Employer or organization.")
    job_title: str = Field(description="Title held by the candidate.")
    location: Location | None = None
    dates: DateRange = Field(default_factory=DateRange)
    current: bool | None = Field(default=None, description="None when current status is not stated.")
    duration_months: int | None = Field(default=None, ge=0, description="Only when stated or reliably derived.")
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    skills_used: list[Skill] = Field(default_factory=list)
    domain: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_current_dates(self) -> Experience:
        if self.current is True and self.dates.end_date is not None:
            raise ValueError("current experience cannot have an end_date")
        return self


class Project(DomainModel):
    name: str = Field(description="Project name.")
    description: str | None = None
    role: str | None = None
    technologies: list[Skill] = Field(default_factory=list)
    domain: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    url: str | None = None


class CandidateProfile(DomainModel):
    """Normalized candidate representation for extraction and downstream matching."""

    identity: CandidateIdentity = Field(default_factory=CandidateIdentity)
    professional_title: str | None = None
    professional_summary: str | None = None
    seniority: SeniorityLevel | None = None
    total_years_experience: float | None = Field(default=None, ge=0)
    domains: list[str] = Field(default_factory=list)
    technical_skills: list[Skill] = Field(default_factory=list)
    programming_languages: list[Skill] = Field(default_factory=list)
    frameworks: list[Skill] = Field(default_factory=list)
    libraries: list[Skill] = Field(default_factory=list)
    databases: list[Skill] = Field(default_factory=list)
    cloud_platforms: list[Skill] = Field(default_factory=list)
    devops_infrastructure: list[Skill] = Field(default_factory=list)
    bi_data_tools: list[Skill] = Field(default_factory=list)
    ai_ml_technologies: list[Skill] = Field(default_factory=list)
    soft_skills: list[Skill] = Field(default_factory=list)
    experiences: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    work_preferences: WorkPreferences = Field(default_factory=WorkPreferences)
    professionally_relevant_interests: list[str] = Field(default_factory=list)
    source_language: str | None = Field(default=None, description="Detected source language, such as fr or en.")
    source_type: str | None = Field(default=None, description="cv, form, email, or other source identifier.")
    raw_text: str | None = Field(default=None, description="Optional source text retained for traceability.")

    @field_validator("total_years_experience")
    @classmethod
    def reject_nan(cls, value: float | None) -> float | None:
        if value is not None and value != value:
            raise ValueError("total_years_experience must be a finite number")
        return value
