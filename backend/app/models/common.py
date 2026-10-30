"""Shared canonical domain models for candidate and job profiles."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic_extra_types.currency_code import ISO4217

SCHEMA_VERSION: Literal["2"] = "2"

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NonNegativeFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]


def _validate_http_url(value: str) -> str:
    # CVs often write "linkedin.com/in/name"; treat a scheme-less host/path as HTTPS rather than rejecting it.
    if "://" not in value and re.match(r"^[\w-]+(\.[\w-]+)+(/|$)", value):
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must be an absolute HTTP or HTTPS URL")
    return value


HttpUrlStr = Annotated[str, AfterValidator(_validate_http_url)]


class DomainModel(BaseModel):
    """Base model configured for LLM JSON input and stable serialization."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Evidenced(DomainModel):
    """Traceability fields shared by every extracted item."""

    evidence: str | None = Field(default=None, description="Exact source text supporting this item.")
    confidence: float | None = Field(default=None, ge=0, le=1, description="Extractor confidence in [0, 1].")
    verified: bool | None = Field(
        default=None, description="Whether the evidence was found in the source text; None when not checked yet."
    )


class SkillLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class LanguageLevel(StrEnum):
    """CEFR levels, plus native."""

    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"
    NATIVE = "native"


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


class WorkSchedule(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"


class RequirementKind(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"


class SkillCategory(StrEnum):
    PROGRAMMING_LANGUAGE = "programming_language"
    FRAMEWORK = "framework"
    LIBRARY = "library"
    DATABASE = "database"
    CLOUD = "cloud"
    DEVOPS = "devops"
    DATA_BI = "data_bi"
    AI_ML = "ai_ml"
    TOOL = "tool"
    METHODOLOGY = "methodology"
    DOMAIN_KNOWLEDGE = "domain_knowledge"
    SOFT_SKILL = "soft_skill"
    OTHER = "other"


class CompensationPeriod(StrEnum):
    HOUR = "hour"
    DAY = "day"
    MONTH = "month"
    YEAR = "year"


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

    def months(self) -> int | None:
        """Whole months between start and end, when both are known."""
        if self.start_date is None or self.end_date is None:
            return None
        return (self.end_date.year - self.start_date.year) * 12 + self.end_date.month - self.start_date.month


class Skill(Evidenced):
    """A canonical skill with optional evidence and source wording."""

    name: NonEmptyStr = Field(description="Canonical English/internal skill name.")
    raw_name: str | None = Field(default=None, description="Skill wording found in the source.")
    category: SkillCategory | None = None
    level: SkillLevel | None = Field(default=None, description="Only set when supported by evidence.")
    years_experience: NonNegativeFloat | None = Field(default=None, description="Explicit or reliably derived years.")
    source: str | None = Field(default=None, description="Extraction source, such as cv or form.")


class SkillRequirement(Evidenced):
    """A job skill requirement, preserving required versus preferred semantics."""

    name: NonEmptyStr = Field(description="Canonical English/internal skill name.")
    raw_name: str | None = Field(default=None, description="Original requirement wording.")
    category: SkillCategory | None = None
    requirement: RequirementKind = Field(description="Whether this skill is required or preferred.")
    level: SkillLevel | None = Field(default=None, description="Only when explicitly stated.")
    minimum_years: NonNegativeFloat | None = Field(default=None, description="Explicit minimum years for this skill.")


class Education(Evidenced):
    institution: NonEmptyStr = Field(description="School or university name.")
    degree: str | None = Field(default=None, description="Degree or qualification.")
    field_of_study: str | None = Field(default=None, description="Major or field of study.")
    location: Location | None = None
    dates: DateRange = Field(default_factory=DateRange)
    grade_or_honors: str | None = Field(default=None, description="Grade, distinction, or honors if stated.")


class Certification(Evidenced):
    name: NonEmptyStr = Field(description="Certification name.")
    issuer: str | None = None
    issue_date: date | None = None
    expiration_date: date | None = None
    credential_id: str | None = None
    url: HttpUrlStr | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Certification:
        if self.issue_date and self.expiration_date and self.expiration_date < self.issue_date:
            raise ValueError("expiration_date must be on or after issue_date")
        return self


class Language(Evidenced):
    language: NonEmptyStr = Field(description="Language name.")
    level: LanguageLevel | None = Field(default=None, description="CEFR level, only when stated or certified.")
    certification: str | None = Field(default=None, description="Language certification if explicitly mentioned.")


class Compensation(DomainModel):
    minimum: Decimal | None = Field(default=None, ge=0, description="Minimum compensation amount.")
    maximum: Decimal | None = Field(default=None, ge=0, description="Maximum compensation amount.")
    currency: ISO4217 | None = Field(default=None, description="ISO 4217 currency code.")
    period: CompensationPeriod | None = None

    @model_validator(mode="after")
    def validate_range(self) -> Compensation:
        if self.minimum is not None and self.maximum is not None and self.maximum < self.minimum:
            raise ValueError("maximum compensation must be on or after minimum compensation")
        return self


class EducationRequirement(Evidenced):
    degree: str | None = None
    field_of_study: str | None = None
    requirement: RequirementKind = Field(description="Whether education is required or preferred.")
    equivalent_education: str | None = Field(
        default=None, description="Explicitly accepted equivalent experience or education."
    )


class ExperienceRequirement(Evidenced):
    minimum_years: NonNegativeFloat | None = None
    maximum_years: NonNegativeFloat | None = None
    relevant_domains: list[str] = Field(default_factory=list)
    required_seniority: SeniorityLevel | None = None

    @model_validator(mode="after")
    def validate_year_range(self) -> ExperienceRequirement:
        if (
            self.minimum_years is not None
            and self.maximum_years is not None
            and self.maximum_years < self.minimum_years
        ):
            raise ValueError("maximum_years must be on or after minimum_years")
        return self


class WorkPreferences(DomainModel):
    preferred_locations: list[Location] = Field(default_factory=list)
    preferred_work_modes: list[WorkMode] = Field(default_factory=list)
    preferred_contract_types: list[ContractType] = Field(default_factory=list)
    preferred_schedules: list[WorkSchedule] = Field(default_factory=list)
    willing_to_relocate: bool | None = Field(default=None, description="Only set when explicitly provided.")
    availability: str | None = Field(default=None, description="Original availability statement.")
    work_authorization: str | None = Field(default=None, description="Explicit authorization or visa statement.")
