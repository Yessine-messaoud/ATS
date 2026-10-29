"""Canonical job profile models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import (
    SCHEMA_VERSION,
    Compensation,
    ContractType,
    DomainModel,
    EducationRequirement,
    Evidenced,
    ExperienceRequirement,
    HttpUrlStr,
    LanguageLevel,
    Location,
    NonEmptyStr,
    RequirementKind,
    SeniorityLevel,
    SkillRequirement,
    WorkMode,
    WorkSchedule,
)


class JobLanguageRequirement(Evidenced):
    language: NonEmptyStr = Field(description="Language name.")
    requirement: RequirementKind = Field(description="Whether the language is required or preferred.")
    level: LanguageLevel | None = Field(default=None, description="Minimum CEFR level when explicitly stated.")


class JobCertificationRequirement(Evidenced):
    name: NonEmptyStr = Field(description="Certification name.")
    requirement: RequirementKind = Field(description="Whether certification is required or preferred.")
    issuer: str | None = None


class JobProfile(DomainModel):
    """Normalized job representation for deterministic and semantic matching.

    Persistence concerns (id, timestamps, raw description text) live on the database records.
    """

    schema_version: Literal["2"] = SCHEMA_VERSION
    title: NonEmptyStr = Field(description="Canonical job title.")
    company: str | None = None
    department_or_team: str | None = None
    job_url: HttpUrlStr | None = None
    job_reference: str | None = None
    contract_type: ContractType | None = None
    schedule: WorkSchedule | None = None
    seniority: SeniorityLevel | None = None
    location: Location | None = None
    work_mode: WorkMode | None = None
    travel_requirements: str | None = None
    experience: ExperienceRequirement = Field(default_factory=ExperienceRequirement)
    skill_requirements: list[SkillRequirement] = Field(default_factory=list)
    education_requirements: list[EducationRequirement] = Field(default_factory=list)
    language_requirements: list[JobLanguageRequirement] = Field(default_factory=list)
    certification_requirements: list[JobCertificationRequirement] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    industry: list[str] = Field(default_factory=list)
    business_domains: list[str] = Field(default_factory=list)
    technical_domains: list[str] = Field(default_factory=list)
    compensation: Compensation | None = None
    benefits: list[str] = Field(default_factory=list)
    visa_sponsorship: bool | None = Field(
        default=None, description="None when the offer does not state sponsorship policy."
    )
    work_authorization: str | None = None
    relocation_support: bool | None = None
    availability: str | None = Field(default=None, description="Expected start date or availability statement.")
    security_clearance: str | None = None
    drivers_license_required: bool | None = None
    other_constraints: list[str] = Field(default_factory=list)
    source_language: str | None = None
