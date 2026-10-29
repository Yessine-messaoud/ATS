# Canonical profile models

The backend models in `backend/app/models` are deliberately independent from FastAPI routes and SQLAlchemy persistence records (`backend/app/db`).

## Design decisions

- `CandidateProfile` and `JobProfile` use canonical English field names. `raw_name`, `raw`, `evidence` and `source_language` preserve extraction context.
- **The profiles are the LLM structured-output schema.** They therefore contain no persistence fields (no `id`, no timestamps). Each profile carries a `schema_version` ("2"). IDs, timestamps and the raw source text live on the database records.
- **Raw text is kept out of profiles.** It is stored only on `DocumentRecord`, so it can be purged under the retention policy without touching structured data.
- Unknown scalar values are `None`, and collections default to empty lists, so an explicit `False` stays distinct from "not stated".
- **One skill list.** Candidate skills live in a single `skills: list[Skill]`, grouped by the `SkillCategory` enum. Job skills use `SkillRequirement.requirement` to keep required and preferred apart.
- **Traceability.** Every extracted item (skill, experience, education, project, certification, language, requirement) inherits `Evidenced`:
  - `evidence`: the exact source text;
  - `confidence`: a value in [0, 1];
  - `verified`: `None` until the evidence verifier has checked that the quote exists in the source document.
- **Shared levels.** `SkillLevel` (beginner to expert) is used for skills and `LanguageLevel` (CEFR A1–C2, plus native) for languages, on both the candidate and the job side, so they can be compared directly.
- **Contract and schedule are separate.** `ContractType` (permanent, internship, freelance, ...) is independent from `WorkSchedule` (full-time or part-time).
- **Validation rules:**
  - names are non-empty;
  - year counts are finite and non-negative;
  - URLs must be absolute http(s);
  - currencies must be valid ISO 4217 codes and are upper-cased;
  - date ranges must be ordered;
  - a stated `duration_months` must match the dates within 2 months;
  - extra keys are rejected (`extra="forbid"`), which matches strict structured outputs.
- `EmailStr` validates syntax but does not verify mailbox ownership.

Sensitive or unreliable fields are intentionally excluded: age, date of birth, gender, ethnicity, religion, marital status, photograph, health data, national identifiers and inferred personality traits. They are irrelevant or risky for fair job matching. Work authorization and visa information are included only as explicit statements, because they can be operationally relevant and are legally sensitive.

## Example usage

LLM JSON should be treated as untrusted input and validated at the extraction boundary:

```python
from app.models import CandidateProfile, JobProfile

candidate = CandidateProfile.model_validate(llm_candidate_json)
job = JobProfile.model_validate(llm_job_json)

# JSON schema to send as the LLM structured-output format:
schema = CandidateProfile.model_json_schema()
```

Full runnable payloads are in `backend/examples/profiles.py`. Validation tests are in `backend/tests/test_models.py`.
