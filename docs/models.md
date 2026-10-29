# Canonical profile models

The backend models in `backend/app/models` are deliberately independent from FastAPI routes and SQLAlchemy persistence models.

## Design decisions

- `CandidateProfile` and `JobProfile` use canonical English field names, while `raw_name`, `raw`, `evidence`, `source_language`, and `raw_text` preserve extraction context.
- Unknown scalar values are `None`; collections default to empty lists. Explicit booleans therefore remain distinct from an unstated value.
- Candidate skills are grouped for practical extraction, but every item is the reusable `Skill` model. Job skills use `SkillRequirement.requirement` to preserve required versus preferred semantics.
- Dates, numeric experience, and salary ranges receive only lightweight consistency checks. Skill normalization, embeddings, ranking, and matching stay in separate services.
- `EmailStr` validates syntax but does not verify mailbox ownership. URLs in identity are retained as strings because source-specific profile URLs can require additional policy later.

Sensitive or unreliable fields intentionally excluded include age, date of birth, gender, ethnicity, religion, marital status, photograph, health data, national identifiers, and inferred personality traits. They are irrelevant or risky for fair job matching. Work authorization and visa information are included only as explicit statements because they can be operationally relevant and legally sensitive.

## Example usage

LLM JSON should be treated as untrusted input and validated at the extraction boundary:

```python
from app.models import CandidateProfile, JobProfile

candidate = CandidateProfile.model_validate(llm_candidate_json)
job = JobProfile.model_validate(llm_job_json)

# Pass validated objects to a separate matching service.
result = matching_service.compare(candidate, job)
```

For runnable complete payloads, see `backend/examples/profiles.py`. For validation coverage, see `backend/tests/test_models.py`.
