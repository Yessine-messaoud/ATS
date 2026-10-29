"""Shared canonical domain models for candidate and job profiles."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class DomainModel(BaseModel):
    """Base model configured for LLM JSON input and stable serialization."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProficiencyLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"
    NATIVE = "native"
    FLUENT = "fluent"


class SeniorityLevel(StrEnum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"
    DIRECTOR = "director"
    EXECUTIVE = "executive"


class WorkMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ON_SITE = "on_site"


class ContractType(StrEnum):
    PERMANENT = "permanent"
    FIXED_TERM = "fixed_term"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    APPRENTICESHIP = "apprenticeship"
    FREELANCE = "freelance"
    CONTRACTOR = "contractor"
    PART_TIME = "part_time"
    FULL_TIME = "full_time"


class RequirementKind(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"


class Location(DomainModel):
    """A normalized location while retaining source wording."""

    city: str | None = Field(default=None, description="Normalized city name.")
    region: str | None = Field(default=None, description="State, province, or region.")
    country: str | None = Field(default=None, description="Normalized country name.")
    raw: str | None = Field(default=None, description="Original location text.")


class DateRange(DomainModel):
    start_date: date | None = Field(default=None, description="Known start date.")
    end_date: date | None = Field(default=None, description="Known end date.")

    @model_validator(mode="after")
    def validate_order(self) -> DateRange:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class Skill(DomainModel):
    """A canonical skill with optional evidence and source wording."""

    name: str = Field(description="Canonical English/internal skill name.")
    raw_name: str | None = Field(default=None, description="Skill wording found in the source.")
    category: str | None = Field(default=None, description="Canonical category, such as database or framework.")
    proficiency: ProficiencyLevel | None = Field(default=None, description="Only set when supported by evidence.")
    years_experience: float | None = Field(default=None, ge=0, description="Explicit or reliably derived years.")
    evidence: str | None = Field(default=None, description="Source text supporting this skill.")
    source: str | None = Field(default=None, description="Extraction source, such as cv or form.")


class SkillRequirement(DomainModel):
    """A job skill requirement, preserving required versus preferred semantics."""

    name: str = Field(description="Canonical English/internal skill name.")
    raw_name: str | None = Field(default=None, description="Original requirement wording.")
    category: str | None = Field(default=None, description="Canonical skill category.")
    requirement: RequirementKind = Field(description="Whether this skill is required or preferred.")
    proficiency: ProficiencyLevel | None = Field(default=None, description="Only when explicitly stated.")
    minimum_years: float | None = Field(default=None, ge=0, description="Explicit minimum years for this skill.")
    evidence: str | None = Field(default=None, description="Source text supporting this requirement.")


class Education(DomainModel):
    institution: str = Field(description="School or university name.")
    degree: str | None = Field(default=None, description="Degree or qualification.")
    field_of_study: str | None = Field(default=None, description="Major or field of study.")
    location: Location | None = None
    dates: DateRange = Field(default_factory=DateRange)
    grade_or_honors: str | None = Field(default=None, description="Grade, distinction, or honors if stated.")


class Certification(DomainModel):
    name: str = Field(description="Certification name.")
    issuer: str | None = None
    issue_date: date | None = None
    expiration_date: date | None = None
    credential_id: str | None = None
    url: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Certification:
        if self.issue_date and self.expiration_date and self.expiration_date < self.issue_date:
            raise ValueError("expiration_date must be on or after issue_date")
        return self


class Language(DomainModel):
    language: str = Field(description="Language name.")
    proficiency: ProficiencyLevel | None = Field(default=None, description="Only when stated or certified.")
    certification: str | None = Field(default=None, description="Language certification if explicitly mentioned.")


class Compensation(DomainModel):
    minimum: Decimal | None = Field(default=None, ge=0, description="Minimum compensation amount.")
    maximum: Decimal | None = Field(default=None, ge=0, description="Maximum compensation amount.")
    currency: str | None = Field(default=None, min_length=3, max_length=3, description="ISO 4217 currency code.")
    period: str | None = Field(default=None, description="Compensation period, such as year or month.")

    @model_validator(mode="after")
    def validate_range(self) -> Compensation:
        if self.minimum is not None and self.maximum is not None and self.maximum < self.minimum:
            raise ValueError("maximum compensation must be on or after minimum compensation")
        return self


class EducationRequirement(DomainModel):
    degree: str | None = None
    field_of_study: str | None = None
    requirement: RequirementKind = Field(description="Whether education is required or preferred.")
    equivalent_education: str | None = Field(default=None, description="Explicitly accepted equivalent experience or education.")
    evidence: str | None = None


class ExperienceRequirement(DomainModel):
    minimum_years: float | None = Field(default=None, ge=0)
    maximum_years: float | None = Field(default=None, ge=0)
    relevant_domains: list[str] = Field(default_factory=list)
    required_seniority: SeniorityLevel | None = None
    evidence: str | None = None

    @model_validator(mode="after")
    def validate_year_range(self) -> ExperienceRequirement:
        if self.minimum_years is not None and self.maximum_years is not None and self.maximum_years < self.minimum_years:
            raise ValueError("maximum_years must be on or after minimum_years")
        return self


class UrlModel(DomainModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute HTTP or HTTPS URL")
        return value


class WorkPreferences(DomainModel):
    preferred_locations: list[Location] = Field(default_factory=list)
    preferred_work_modes: list[WorkMode] = Field(default_factory=list)
    preferred_contract_types: list[ContractType] = Field(default_factory=list)
    willing_to_relocate: bool | None = Field(default=None, description="Only set when explicitly provided.")
    availability: str | None = Field(default=None, description="Original availability statement.")
    work_authorization: str | None = Field(default=None, description="Explicit authorization or visa statement.")
