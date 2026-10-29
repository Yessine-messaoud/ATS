"""Canonical candidate profile models."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import EmailStr, Field, model_validator

from .common import (
    SCHEMA_VERSION,
    Certification,
    DateRange,
    DomainModel,
    Education,
    Evidenced,
    HttpUrlStr,
    Language,
    Location,
    NonEmptyStr,
    NonNegativeFloat,
    SeniorityLevel,
    Skill,
    WorkPreferences,
)

# Tolerance between a stated duration and the one derived from dates (partial months, rounding).
DURATION_TOLERANCE_MONTHS = 2


class SourceType(StrEnum):
    CV = "cv"
    FORM = "form"
    EMAIL = "email"
    OTHER = "other"


class CandidateIdentity(DomainModel):
    full_name: str | None = Field(default=None, description="Candidate's full name if provided.")
    email: EmailStr | None = Field(default=None, description="Candidate email address.")
    phone: str | None = Field(default=None, description="Phone number as supplied; avoid guessing country codes.")
    location: Location | None = None
    linkedin_url: HttpUrlStr | None = None
    github_url: HttpUrlStr | None = None
    portfolio_url: HttpUrlStr | None = None


class Experience(Evidenced):
    company: NonEmptyStr = Field(description="Employer or organization.")
    job_title: NonEmptyStr = Field(description="Title held by the candidate.")
    location: Location | None = None
    dates: DateRange = Field(default_factory=DateRange)
    current: bool | None = Field(default=None, description="None when current status is not stated.")
    duration_months: int | None = Field(default=None, ge=0, description="Only when stated or reliably derived.")
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    skills_used: list[Skill] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self) -> Experience:
        if self.current is True and self.dates.end_date is not None:
            raise ValueError("current experience cannot have an end_date")
        derived = self.dates.months()
        if (
            self.duration_months is not None
            and derived is not None
            and abs(self.duration_months - derived) > DURATION_TOLERANCE_MONTHS
        ):
            raise ValueError(f"duration_months={self.duration_months} contradicts dates ({derived} months)")
        return self


class Project(Evidenced):
    name: NonEmptyStr = Field(description="Project name.")
    description: str | None = None
    role: str | None = None
    technologies: list[Skill] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    url: HttpUrlStr | None = None


class CandidateProfile(DomainModel):
    """Normalized candidate representation for extraction and downstream matching.

    Persistence concerns (id, timestamps, raw source text) live on the database records, not here,
    so that this model can be used directly as the LLM structured-output schema.
    """

    schema_version: Literal["2"] = SCHEMA_VERSION
    identity: CandidateIdentity = Field(default_factory=CandidateIdentity)
    professional_title: str | None = None
    professional_summary: str | None = None
    seniority: SeniorityLevel | None = None
    total_years_experience: NonNegativeFloat | None = None
    domains: list[str] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list, description="All skills; grouped through Skill.category.")
    experiences: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    work_preferences: WorkPreferences = Field(default_factory=WorkPreferences)
    professionally_relevant_interests: list[str] = Field(default_factory=list)
    source_language: str | None = Field(default=None, description="Detected source language, such as fr or en.")
    source_type: SourceType | None = None
