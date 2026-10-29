"""Extraction pipeline: LLM tool call -> validation with correction loop -> partial validation -> evidence check."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from app.models import CandidateProfile, JobProfile

from .evidence import EvidenceStats, verify_evidence
from .llm import LLMClient, ToolCallResult, ToolSpec
from .prompts import CV_PROMPT_VERSION, CV_SYSTEM_PROMPT, JOB_PROMPT_VERSION, JOB_SYSTEM_PROMPT, document_prompt
from .sections import detect_sections
from .validation import ValidationIssue, format_errors, validate_partially

# Fields the system sets itself; hidden from the schema the model fills in.
SYSTEM_FIELDS = {"verified", "schema_version"}


class ExtractionFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class ExtractionTarget[M: BaseModel]:
    model: type[M]
    kind: str
    tool_name: str
    tool_description: str
    system_prompt: str
    prompt_version: str


CANDIDATE_TARGET = ExtractionTarget(
    model=CandidateProfile,
    kind="cv",
    tool_name="record_candidate_profile",
    tool_description="Record the structured candidate profile extracted from the document.",
    system_prompt=CV_SYSTEM_PROMPT,
    prompt_version=CV_PROMPT_VERSION,
)
JOB_TARGET = ExtractionTarget(
    model=JobProfile,
    kind="job_description",
    tool_name="record_job_profile",
    tool_description="Record the structured job requirements extracted from the job description.",
    system_prompt=JOB_SYSTEM_PROMPT,
    prompt_version=JOB_PROMPT_VERSION,
)


@dataclass
class ExtractionResult[M: BaseModel]:
    profile: M
    issues: list[ValidationIssue]
    evidence: EvidenceStats
    meta: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            **self.meta,
            "issues": [asdict(issue) for issue in self.issues],
            "evidence": {**asdict(self.evidence), "unverified_rate": round(self.evidence.unverified_rate, 3)},
        }


def _strip_system_fields(schema: Any) -> Any:
    if isinstance(schema, dict):
        cleaned = {key: _strip_system_fields(value) for key, value in schema.items()}
        if isinstance(cleaned.get("properties"), dict):
            cleaned["properties"] = {k: v for k, v in cleaned["properties"].items() if k not in SYSTEM_FIELDS}
            if "required" in cleaned:
                cleaned["required"] = [k for k in cleaned["required"] if k not in SYSTEM_FIELDS]
        return cleaned
    if isinstance(schema, list):
        return [_strip_system_fields(item) for item in schema]
    return schema


def tool_spec(target: ExtractionTarget[Any]) -> ToolSpec:
    return ToolSpec(
        name=target.tool_name,
        description=target.tool_description,
        input_schema=_strip_system_fields(target.model.model_json_schema()),
    )


def extract[M: BaseModel](
    llm: LLMClient, target: ExtractionTarget[M], text: str, *, max_repairs: int
) -> ExtractionResult[M]:
    sections = detect_sections(text)
    hints = ", ".join(dict.fromkeys(section.name for section in sections))
    session = llm.session(system=target.system_prompt, tool=tool_spec(target))

    calls: list[ToolCallResult] = [session.start(document_prompt(text, kind=target.kind, section_hints=hints))]
    profile: M | None = None
    issues: list[ValidationIssue] = []
    for attempt in range(max_repairs + 1):
        data = calls[-1].data
        if data is not None:
            try:
                profile = target.model.model_validate(data)
                break
            except ValidationError as exc:
                feedback = (
                    f"The record failed validation:\n{format_errors(exc)}\n"
                    f"Call `{target.tool_name}` again with the complete corrected record."
                )
        else:
            feedback = f"You did not call the tool. Call `{target.tool_name}` with the complete record."
        if attempt < max_repairs:
            calls.append(session.correct(feedback))

    if profile is None:
        last_data = next((call.data for call in reversed(calls) if call.data is not None), None)
        if last_data is None:
            raise ExtractionFailed("the model never returned a record")
        profile, issues = validate_partially(target.model, last_data)
        if profile is None:
            raise ExtractionFailed(f"the record could not be repaired: {issues[-1].path}: {issues[-1].message}")

    evidence = verify_evidence(profile, text)
    meta = {
        "model": calls[-1].model,
        "prompt_version": target.prompt_version,
        "llm_calls": len(calls),
        "input_tokens": sum(call.input_tokens for call in calls),
        "output_tokens": sum(call.output_tokens for call in calls),
        "latency_ms": sum(call.latency_ms for call in calls),
        "request_ids": [call.request_id for call in calls if call.request_id],
        "sections": [section.name for section in sections],
    }
    return ExtractionResult(profile=profile, issues=issues, evidence=evidence, meta=meta)
