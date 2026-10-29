"""Canonical job profile models."""

from __future__ import annotations

from pydantic import Field

from .common import (
    Certification,
    Compensation,
    ContractType,
    DomainModel,
    EducationRequirement,
    ExperienceRequirement,
    Language,
    Location,
    RequirementKind,
    SkillRequirement,
    SeniorityLevel,
    WorkMode,
)


class JobLanguageRequirement(DomainModel):
    language: str = Field(description="Language name.")
    requirement: RequirementKind = Field(description="Whether the language is required or preferred.")
    proficiency: str | None = Field(default=None, description="Required level when explicitly stated.")
    evidence: str | None = None


class JobCertificationRequirement(DomainModel):
    name: str = Field(description="Certification name.")
    requirement: RequirementKind = Field(description="Whether certification is required or preferred.")
    issuer: str | None = None
    evidence: str | None = None


class JobProfile(DomainModel):
    """Normalized job representation for deterministic and semantic matching."""

    title: str = Field(description="Canonical job title.")
    company: str | None = None
    department_or_team: str | None = None
    job_url: str | None = None
    job_reference: str | None = None
    contract_type: ContractType | None = None
    employment_type: str | None = Field(default=None, description="Full-time, part-time, or source-specific employment label.")
    seniority: SeniorityLevel | None = None
    location: Location | None = None
    country: str | None = None
    work_mode: WorkMode | None = None
    travel_requirements: str | None = None
    experience: ExperienceRequirement = Field(default_factory=ExperienceRequirement)
    skill_requirements: list[SkillRequirement] = Field(default_factory=list)
    education_requirements: list[EducationRequirement] = Field(default_factory=list)
    language_requirements: list[JobLanguageRequirement] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    certification_requirements: list[JobCertificationRequirement] = Field(default_factory=list)
    industry: list[str] = Field(default_factory=list)
    business_domains: list[str] = Field(default_factory=list)
    technical_domains: list[str] = Field(default_factory=list)
    compensation: Compensation | None = None
    benefits: list[str] = Field(default_factory=list)
    visa_sponsorship: bool | None = Field(default=None, description="None when the offer does not state sponsorship policy.")
    work_authorization: str | None = None
    relocation_support: bool | None = None
    availability: str | None = None
    travel: str | None = None
    security_clearance: str | None = None
    drivers_license_required: bool | None = None
    other_constraints: list[str] = Field(default_factory=list)
    source_language: str | None = None
    raw_text: str | None = Field(default=None, description="Optional source job description for traceability.")
