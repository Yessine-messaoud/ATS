"""Agent tools: thin wrappers over the existing services.

Read-only tools run immediately. Tools with side effects (`requires_confirmation`) are never executed by the
model: the loop pauses and a recruiter confirms or declines each call. Outputs never include contact details
(email, phone, links) or raw CV text, and honour blind mode.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import ApplicationRecord, ApplicationStage, CandidateRecord, DocumentRecord, JobRecord
from app.extraction.llm import ToolSpec
from app.matching.explain import template_explanation
from app.matching.skills import normalize_text
from app.models import CandidateProfile, JobProfile, RequirementKind
from app.search.retrieval import hybrid_search
from app.services.matching import blind_label, rank_candidates, recommend_jobs, score
from app.services.pipeline import AlreadyInPipeline, add_to_pipeline, job_applications, move_application

AGENT_ACTOR = "recruiter (via assistant)"


class ToolError(Exception):
    """Reported to the model as an `is_error` tool result."""


@dataclass
class ToolContext:
    db: Session
    blind: bool
    full_scoring_limit: int
    retrieval_k: int
    consent_required: bool = False


# --- inputs ----------------------------------------------------------------------------------------------------------


class ListJobsIn(BaseModel):
    status: Literal["open", "closed", "all"] = "open"


class SearchCandidatesIn(BaseModel):
    query: str = Field(min_length=2, description="Skills, role or domain, e.g. 'data engineer spark azure'.")
    limit: int = Field(default=10, ge=1, le=30)


class CandidateIdIn(BaseModel):
    candidate_id: uuid.UUID


class JobIdIn(BaseModel):
    job_id: uuid.UUID


class RankIn(BaseModel):
    job_id: uuid.UUID
    limit: int = Field(default=10, ge=1, le=50)


class PairIn(BaseModel):
    candidate_id: uuid.UUID
    job_id: uuid.UUID


class RecommendIn(BaseModel):
    candidate_id: uuid.UUID
    limit: int = Field(default=5, ge=1, le=20)


class MoveIn(BaseModel):
    application_id: uuid.UUID
    stage: ApplicationStage
    reason: str | None = Field(
        default=None, max_length=300, description="Short justification recorded in the audit log."
    )


# --- helpers ---------------------------------------------------------------------------------------------------------


def _candidate(ctx: ToolContext, candidate_id: uuid.UUID) -> CandidateRecord:
    record = ctx.db.get(CandidateRecord, candidate_id)
    if record is None:
        raise ToolError(f"no candidate with id {candidate_id}")
    return record


def _job(ctx: ToolContext, job_id: uuid.UUID) -> JobRecord:
    record = ctx.db.get(JobRecord, job_id)
    if record is None:
        raise ToolError(f"no job with id {job_id}")
    return record


def _name(ctx: ToolContext, record: CandidateRecord) -> str:
    name = CandidateProfile.model_validate(record.profile).identity.full_name
    return blind_label(record.id) if ctx.blind or not name else name


def _candidate_brief(ctx: ToolContext, record: CandidateRecord) -> dict[str, Any]:
    profile = CandidateProfile.model_validate(record.profile)
    return {
        "candidate_id": str(record.id),
        "name": _name(ctx, record),
        "title": profile.professional_title,
        "skills": [s.name for s in profile.skills if s.verified is not False][:12],
    }


# --- read-only tools -------------------------------------------------------------------------------------------------


def list_jobs(ctx: ToolContext, args: ListJobsIn) -> Any:
    query = select(JobRecord).order_by(JobRecord.created_at.desc())
    if args.status != "all":
        query = query.where(JobRecord.status == args.status)
    return [
        {
            "job_id": str(job.id),
            "title": job.title,
            "company": job.profile.get("company"),
            "city": (job.profile.get("location") or {}).get("city"),
            "status": job.status,
            "requirements_validated": job.requirements_validated,
        }
        for job in ctx.db.scalars(query)
    ]


def search_candidates(ctx: ToolContext, args: SearchCandidatesIn) -> Any:
    keywords = [w for w in normalize_text(args.query).split() if len(w) > 1]
    hits = hybrid_search(ctx.db, args.query, keywords, k=args.limit)
    query = select(CandidateRecord).where(CandidateRecord.id.in_([h.candidate_id for h in hits]))
    if ctx.consent_required:
        query = query.where(CandidateRecord.talent_pool_consent.is_(True))
    records = {r.id: r for r in ctx.db.scalars(query)}
    return [_candidate_brief(ctx, records[h.candidate_id]) for h in hits if h.candidate_id in records]


def get_candidate(ctx: ToolContext, args: CandidateIdIn) -> Any:
    record = _candidate(ctx, args.candidate_id)
    profile = CandidateProfile.model_validate(record.profile)
    document = ctx.db.get(DocumentRecord, record.source_document_id) if record.source_document_id else None
    return {
        **_candidate_brief(ctx, record),
        "seniority": profile.seniority,
        "total_years_experience": profile.total_years_experience,
        "location": profile.identity.location.city if profile.identity.location else None,
        "skills": [{"name": s.name, "verified": s.verified} for s in profile.skills],
        "experiences": [
            {
                "title": e.job_title,
                "company": e.company,
                "start": e.dates.start_date,
                "end": "present" if e.current else e.dates.end_date,
            }
            for e in profile.experiences
        ],
        "education": [
            {"degree": e.degree, "institution": e.institution, "field": e.field_of_study} for e in profile.education
        ],
        "languages": [{"language": lang.language, "level": lang.level} for lang in profile.languages],
        "certifications": [c.name for c in profile.certifications],
        "document_flags": document.flags if document else [],
    }


def get_job(ctx: ToolContext, args: JobIdIn) -> Any:
    record = _job(ctx, args.job_id)
    profile = JobProfile.model_validate(record.profile)
    return {
        "job_id": str(record.id),
        "title": profile.title,
        "status": record.status,
        "requirements_validated": record.requirements_validated,
        "required_skills": [s.name for s in profile.skill_requirements if s.requirement is RequirementKind.REQUIRED],
        "preferred_skills": [s.name for s in profile.skill_requirements if s.requirement is RequirementKind.PREFERRED],
        "minimum_years": profile.experience.minimum_years,
        "languages": [
            {"language": lang.language, "level": lang.level, "requirement": lang.requirement}
            for lang in profile.language_requirements
        ],
        "location": profile.location.model_dump(exclude_none=True) if profile.location else None,
        "work_mode": profile.work_mode,
        "contract_type": profile.contract_type,
    }


def rank_candidates_for_job(ctx: ToolContext, args: RankIn) -> Any:
    job = _job(ctx, args.job_id)
    run = rank_candidates(
        ctx.db,
        job,
        limit=args.limit,
        full_scoring_limit=ctx.full_scoring_limit,
        retrieval_k=ctx.retrieval_k,
        consent_required=ctx.consent_required,
    )

    def row(ranked: Any) -> dict[str, Any]:
        result = ranked.result
        return {
            "candidate_id": str(ranked.candidate.id),
            "name": _name(ctx, ranked.candidate),
            "score": result.overall_score,
            "missing_required": result.missing_required,
            "knockouts_not_passed": [
                f"{k.criterion}: {k.status.value} ({k.detail})" for k in result.knockouts if k.status.value != "pass"
            ],
        }

    return {
        "job": job.title,
        "requirements_validated": job.requirements_validated,
        "ranked": [row(r) for r in run.passed],
        "not_meeting_mandatory_criteria": [row(r) for r in run.knocked_out],
    }


def explain_match(ctx: ToolContext, args: PairIn) -> Any:
    candidate, job = _candidate(ctx, args.candidate_id), _job(ctx, args.job_id)
    result = score(candidate, job)
    return {
        "candidate": _name(ctx, candidate),
        "job": job.title,
        "overall_score": result.overall_score,
        "score_before_penalty": result.raw_score,
        "passed_mandatory_criteria": result.passed_knockouts,
        "knockouts": [
            {"criterion": k.criterion, "status": k.status.value, "detail": k.detail} for k in result.knockouts
        ],
        "dimensions": [
            {
                "name": d.name,
                "score": round(d.score * 100),
                "weight_percent": round(d.weight * 100),
                "factors": [{"label": f.label, "status": f.status.value, "detail": f.detail} for f in d.factors],
            }
            for d in result.dimensions
        ],
        "missing_required": result.missing_required,
        "ignored_unverified_claims": result.ignored_unverified,
    }


def interview_questions(ctx: ToolContext, args: PairIn) -> Any:
    candidate, job = _candidate(ctx, args.candidate_id), _job(ctx, args.job_id)
    explanation = template_explanation(score(candidate, job))
    return {
        "questions": [q.question for q in explanation.interview_questions],
        "gaps_to_probe": [g.text for g in explanation.gaps],
    }


def recommend_jobs_for_candidate(ctx: ToolContext, args: RecommendIn) -> Any:
    candidate = _candidate(ctx, args.candidate_id)
    return [
        {
            "job_id": str(r.job.id),
            "title": r.job.title,
            "score": r.result.overall_score,
            "passed_mandatory_criteria": r.result.passed_knockouts,
            "missing_required": r.result.missing_required,
        }
        for r in recommend_jobs(ctx.db, candidate, limit=args.limit, consent_required=ctx.consent_required)
    ]


def get_pipeline(ctx: ToolContext, args: JobIdIn) -> Any:
    job = _job(ctx, args.job_id)
    return [
        {
            "application_id": str(a.id),
            "candidate_id": str(a.candidate_id),
            "name": _name(ctx, a.candidate),
            "stage": a.stage.value,
        }
        for a in job_applications(ctx.db, job)
    ]


# --- tools with side effects (executed only after a recruiter confirms) -----------------------------------------------


def add_candidate_to_pipeline(ctx: ToolContext, args: PairIn) -> Any:
    candidate, job = _candidate(ctx, args.candidate_id), _job(ctx, args.job_id)
    try:
        application = add_to_pipeline(ctx.db, candidate, job, actor=AGENT_ACTOR)
    except AlreadyInPipeline as exc:
        raise ToolError(str(exc)) from exc
    return {"application_id": str(application.id), "stage": application.stage.value}


def move_application_stage(ctx: ToolContext, args: MoveIn) -> Any:
    application = ctx.db.get(ApplicationRecord, args.application_id)
    if application is None:
        raise ToolError(f"no application with id {args.application_id}")
    previous = application.stage.value
    move_application(ctx.db, application, args.stage, actor=AGENT_ACTOR, reason=args.reason)
    return {"application_id": str(application.id), "from": previous, "to": application.stage.value}


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    input_model: type[BaseModel]
    run: Callable[[ToolContext, Any], Any]
    requires_confirmation: bool = False

    def spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description, input_schema=self.input_model.model_json_schema())


TOOLS: dict[str, AgentTool] = {
    tool.name: tool
    for tool in [
        AgentTool(
            "list_jobs",
            "List jobs (open by default) with their ids. Use it to find a job id from a title.",
            ListJobsIn,
            list_jobs,
        ),
        AgentTool(
            "search_candidates",
            "Find candidates in the talent pool by skills, role or domain (hybrid semantic + keyword search). Returns "
            "ids, names (unless blind mode) and main skills. Not a score: use rank_candidates_for_job or "
            "explain_match for scores.",
            SearchCandidatesIn,
            search_candidates,
        ),
        AgentTool(
            "get_candidate",
            "Professional profile of a candidate: skills (with verification status), experience, education, "
            "languages, document flags. No contact details.",
            CandidateIdIn,
            get_candidate,
        ),
        AgentTool(
            "get_job",
            "Requirements of a job: required/preferred skills, minimum years, languages, location, work mode.",
            JobIdIn,
            get_job,
        ),
        AgentTool(
            "rank_candidates_for_job",
            "Rank the talent pool for a job with the deterministic scoring engine. Candidates failing a mandatory "
            "criterion are listed separately with the reason.",
            RankIn,
            rank_candidates_for_job,
        ),
        AgentTool(
            "explain_match",
            "Full score breakdown of one candidate for one job: mandatory criteria, dimension scores and every factor.",
            PairIn,
            explain_match,
        ),
        AgentTool(
            "interview_questions",
            "Interview questions targeting the gaps and unknowns of a candidate for a job.",
            PairIn,
            interview_questions,
        ),
        AgentTool(
            "recommend_jobs_for_candidate",
            "Open jobs ranked for a candidate.",
            RecommendIn,
            recommend_jobs_for_candidate,
        ),
        AgentTool(
            "get_pipeline", "A job's hiring pipeline: application ids, candidates and stages.", JobIdIn, get_pipeline
        ),
        AgentTool(
            "add_candidate_to_pipeline",
            "Add a candidate to a job's pipeline (stage 'new'). Requires the recruiter's confirmation, which the "
            "system asks for automatically.",
            PairIn,
            add_candidate_to_pipeline,
            requires_confirmation=True,
        ),
        AgentTool(
            "move_application_stage",
            "Move an application to another stage (screening, interview, offer, hired, rejected, withdrawn). Requires "
            "the recruiter's confirmation, which the system asks for automatically. Get the application id from "
            "get_pipeline.",
            MoveIn,
            move_application_stage,
            requires_confirmation=True,
        ),
    ]
}


def describe_action(ctx: ToolContext, name: str, raw_input: dict[str, Any]) -> str:
    """Human-readable summary of a pending action, for the confirmation prompt."""
    try:
        if name == "add_candidate_to_pipeline":
            args = PairIn.model_validate(raw_input)
            who = _name(ctx, _candidate(ctx, args.candidate_id))
            return f"Add {who} to the pipeline of “{_job(ctx, args.job_id).title}”"
        if name == "move_application_stage":
            move = MoveIn.model_validate(raw_input)
            application = ctx.db.get(ApplicationRecord, move.application_id)
            if application is not None:
                who = _name(ctx, application.candidate)
                reason = f" (reason: {move.reason})" if move.reason else ""
                change = f"from {application.stage.value} to {move.stage.value}"
                return f"Move {who} {change} for “{application.job.title}”{reason}"
    except (ToolError, ValueError):
        pass
    return f"{name}({raw_input})"
