# ATS Project

AI recruitment and job matching platform. See [`description.txt`](../description.txt) for the vision,
[`TODO.md`](../TODO.md) for the roadmap and [`AUDIT.md`](AUDIT.md) for the initial audit.

## Project structure

- `backend/`: FastAPI application (Python 3.12, managed with [uv](https://docs.astral.sh/uv/))
  - `app/models/`: canonical Pydantic profiles (also used as the LLM structured-output schema)
  - `app/db/`: SQLAlchemy records
  - `migrations/`: Alembic migrations
- `frontend/`: Next.js recruiter interface (see [`frontend/README.md`](../frontend/README.md))
- `docker-compose.yml`: Postgres 16 with pgvector, plus the backend container
- `.github/workflows/ci.yml`: lint, type-check, migrations and tests on every push and PR

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/getting-started/installation/), Docker, Node 22+.

```bash
# 1. Secrets (both files are git-ignored). Use the same password in both.
cp .env.example .env
cp backend/.env.example backend/.env

# 2. Database (from the repository root)
docker compose up -d postgres

# 3. Backend
cd backend
uv sync                      # installs Python 3.12 and all dependencies
uv run alembic upgrade head
uv run uvicorn app.main:app --reload    # http://localhost:8000/docs

# 4. Frontend (in another terminal)
cd frontend
npm install
npm run dev                  # http://localhost:3000
```

To run the whole stack in Docker instead: `docker compose up -d --build`, then open http://localhost:3000.
Load demo data without an LLM key: `docker compose exec backend python -m scripts.seed_demo`. The image includes Tesseract, so OCR
for scanned CVs works there. Locally, OCR is skipped (and flagged) unless Tesseract is installed.

### LLM: local (Ollama) or Claude

Extraction, match explanations and the assistant use the provider set by `LLM_PROVIDER`.

- **`ollama` (default).** A local model served by [Ollama](https://ollama.com): free, and CVs never leave the
  machine. Install Ollama, then `ollama pull mistral`. The assistant needs a model with tool calling (`ollama show
  <model>` lists `tools` under Capabilities): mistral, llama3.1 or qwen2.5 work, llama3 (8B, first release) does
  not. `OLLAMA_NUM_GPU=99` (the default) keeps every layer on the GPU. Ollama's own estimate leaves about 25% of a 7B
  model on the CPU of a 6 GB card, which is about 1.7× slower. Check with `ollama ps`: the PROCESSOR column should
  read `100% GPU`. In Docker, the backend reaches the host's Ollama at `host.docker.internal:11434`.
- **`anthropic`.** `claude-opus-5-5`. Set `ANTHROPIC_API_KEY` in `.env` (for Docker) or `backend/.env`, or run
  `ant auth login`. It is more accurate and much faster than a 7B local model.

If the LLM is unreachable, the API still runs: AI endpoints return `503`, and the tests use a scripted fake LLM.

### Accounts and roles (Phase 7)

Everyone signs in. There are three roles:

| Role | Who | Sees |
|---|---|---|
| **Admin** | The platform operator | Every company, account and audit entry. Approves or suspends companies, creates staff accounts, resets passwords, watches CV processing. Does not post jobs. |
| **Recruiter** | A member of a hiring company | Only their company: its jobs, the CVs it uploaded, the people who applied to its jobs, and job-board candidates who opened their profile to all companies. Manages the company profile and team. |
| **Candidate** | A job seeker | The public job board, their own applications (status only, never scores), their profile, and their data (export, delete). |

Create the first accounts from `backend/` (a password is generated and printed once unless `--password` is given):

```bash
uv run python -m scripts.create_user --role admin --email admin@example.com --name "Platform Admin"
uv run python -m scripts.create_user --role recruiter --email rh@demo.test --name "Rania" --company "Demo company"
```

Companies can also sign up at `/signup?type=company`; they start **pending** and their jobs stay off the job board until
an admin approves them (`AUTO_APPROVE_COMPANIES=true` skips this in development). Candidates sign up at `/signup`.

How it works:

- **Sessions.** `POST /api/auth/login` returns an opaque token; the database stores only its SHA-256. The Next.js server
  keeps the token in an httpOnly cookie and forwards it as a bearer token: browsers never read it and never call the API.
  Passwords are hashed with scrypt; 5 failed sign-ins lock an email for 15 minutes; changing a password or deactivating
  an account signs it out everywhere; suspending a company signs out its recruiters.
- **Company isolation** (`app/services/access.py`). Every recruiter query is filtered by company; another company's
  records answer `404`, not `403`. Rankings, the assistant's tools, search, duplicate detection and the audit log are
  scoped the same way. Audit entries carry the company they belong to and name the actor as `user:<id>`.
- **Portal candidates own their profile.** Companies they applied to can read it and decide, but cannot edit, merge,
  export or erase it. When a candidate corrects their profile, anything added or changed is marked unverified, so it
  earns no matching credit: a candidate can remove or fix information, never raise their own score.
- **Background CV reading** (`app/services/tasks.py`). A job-board application stores the CV (encrypted) in
  `ingestion_tasks`; a worker thread in the API reads it (about a minute on a local 7B model), creates or updates the
  profile, then the application. The candidate sees "Reading your CV…" until then. Tasks survive restarts, and LLM
  outages are retried up to `INGESTION_MAX_ATTEMPTS` times.

## API (Phase 1)

| Endpoint | Purpose |
|---|---|
| `POST /api/candidates/upload` | Upload a CV (PDF, DOCX or text) or an application email (`.eml`). Returns the extracted profile with evidence checks and document flags (hidden text, possible prompt injection, OCR). |
| `GET /api/candidates`, `GET /api/candidates/{id}` | List or read candidates. |
| `POST /api/jobs` | `{"text": "<job description>"}` → extracted requirement grid (not yet validated). |
| `PUT /api/jobs/{id}/requirements` | Recruiter-validated `JobProfile`; marks the grid as the matching reference. |
| `GET /api/jobs`, `GET /api/jobs/{id}` | List or read jobs. |
| `PUT /api/jobs/{id}/weights` | Per-job scoring weights (relative), the missing-skill penalty, and knock-outs on/off. |
| `GET /api/jobs/{id}/ranking?blind=true` | Rank the candidate pool: candidates passing knock-outs, then knocked-out ones with reasons. `blind` hides names. |
| `POST /api/matches` | `{"candidate_id", "job_id", "explain": true}` → full factor breakdown plus an explanation, saved as match history. |
| `GET /api/matches/{id}` | Read a stored match. |
| `GET /api/candidates/{id}/recommendations` | Open jobs ranked for a candidate. |
| `GET /api/candidates/{id}/duplicates` | Possible duplicates (same email or phone, or similar name + near-identical profile). |
| `POST /api/candidates/{id}/merge` | `{"duplicate_id"}`: recruiter-confirmed merge (applications and match history move; audit logged). |
| `POST /api/agent/conversations` | `{"blind": false}`: start an assistant conversation. |
| `POST /api/agent/conversations/{id}/messages` | `{"text"}`: the assistant answers, using tools; actions it proposes are returned as `pending_actions`. |
| `POST /api/agent/conversations/{id}/decisions` | `{"decisions": [{"tool_use_id", "approved"}]}`: confirm or decline proposed actions. |
| `PUT /api/candidates/{id}/consent` | `{"consent": true}`: talent-pool consent (audit logged). |
| `GET /api/candidates/{id}/export` | Everything held about the candidate, as a JSON download (GDPR access and portability). |
| `DELETE /api/candidates/{id}?reason=` | Erase the candidate: profile, documents (merged ones too), applications, scores, and assistant conversations that mention them. Irreversible. |
| `GET /api/audit?entity_id=&action=&actor=&before=` | Audit log, newest first. `action` ending with `.` filters by prefix (`candidate.`). |
| `GET /api/privacy/policy` | Retention periods, encryption and AI set-up, used by the candidate notice (`/privacy`). |

### Search and taxonomy (Phase 4)

- Every candidate and job is indexed for **hybrid retrieval**: an embedding (pgvector, HNSW) plus Postgres full-text
  search, fused with Reciprocal Rank Fusion. Above `FULL_SCORING_LIMIT` candidates (default 500), rankings score the
  retrieval shortlist (`RETRIEVAL_K`, default 200) instead of the whole pool. The order is always the deterministic
  score.
- Rebuild the index with `uv run python -m scripts.reindex` (e.g. after changing the embedding model).
- **ESCO**: download the CSV export (English + French) from https://esco.ec.europa.eu/en/use-esco/download, then run
  `uv run python -m scripts.import_esco <folder> --version esco-1.2.0` and restart the API.

### How a score is computed (`app/matching`, engine `match-v1`)

1. **Knock-outs** (mandatory language level, certification, location/relocation, work authorization): pass, fail
   or unknown. Failing candidates are listed separately, never hidden.
2. **Dimensions**, each scored in [0, 1] and weighted (defaults: required skills 40, preferred 15, experience 20,
   seniority 10, languages 5, education 5, location 5). Dimensions the job does not use are excluded and the weights
   renormalized. Skill credit depends on how a skill is demonstrated (professional use and duration > projects >
   listing, with recency decay) and on the skill graph (PostgreSQL ⟹ SQL). Unverified claims earn nothing.
3. **Penalty**: each missing required skill multiplies the score by 0.92.

No LLM is involved, and identity fields are never read. An optional explanation is generated from the factors only and
checked for faithfulness.

Interactive docs: http://localhost:8000/docs. Extraction quality is measured with the harness in
[`backend/eval/`](../backend/eval/README.md).

## Development

```bash
cd backend
uv run pytest                # DB tests are skipped if Postgres is not running
uv run ruff check . && uv run ruff format .
uv run mypy app tests examples eval scripts migrations/env.py
uv run alembic revision --autogenerate -m "describe change"   # after changing app/db/records.py

# Optional: run the same checks on every commit
uv run pre-commit install --config ../.pre-commit-config.yaml
```


### Privacy and security (Phase 6)

- **Encryption at rest.** Uploaded files and their extracted text are encrypted with Fernet (AES-128-CBC +
  HMAC-SHA256). Generate a key with `uv run python -m app.security.crypto` and set `DOCUMENT_ENCRYPTION_KEYS`. With
  `APP_ENV=production` the API refuses to start without one. To rotate keys, put the new key first
  (`new,old`), run `uv run python -m scripts.encrypt_documents`, then remove the old key. The same script encrypts
  rows written before a key was set. `--decrypt` reverses it.
- **Retention.** `uv run python -m scripts.retention [--dry-run]`, run daily. Document content is deleted after
  `DOCUMENT_RETENTION_DAYS` (180); the metadata and hash stay, so duplicates are still detected. Candidates without
  talent-pool consent and without activity for `CANDIDATE_RETENTION_DAYS` (730) are erased. Everything is audited.
- **Consent.** `REQUIRE_TALENT_POOL_CONSENT=true` limits each job's ranking (and the assistant's searches and
  recommendations) to candidates who consented, plus the job's own applicants.
- **Personal data in logs.** A logging filter masks e-mail addresses and phone numbers in every record, including
  tracebacks.
- **Protected characteristics.** They are removed from extracted profiles by a deterministic pass after the LLM
  (marital status, birth date and age, nationality, religion, gender, health), and requests to filter or judge on
  them are refused by the assistant's policy guard before any model call.
- **Test suites in CI.** `tests/test_fairness.py` holds counterfactual tests: names from several origins, gendered
  French titles and protected mentions must leave the whole match result unchanged. `tests/test_adversarial.py`
  covers hidden text, keyword stuffing and prompt injection: the file must be flagged, planted skills must stay
  unverified, and the score must equal the clean CV's.

### Assistant (Phase 5)

A tool-calling agent (`app/agent`) over the same services: it searches, ranks, explains, compares, prepares interviews
and drafts emails. It cannot set a score (scores come from the engine) and cannot change data on its own: adding to
a pipeline or moving a stage is proposed, then confirmed or declined by the recruiter, and audit-logged.

With a local model, the assistant uses **structured tool calling** by default (`OLLAMA_TOOL_MODE=structured`).

1. A JSON-constrained call picks the next step: a tool from an enum, or `answer`. On the first step it may only pick
   a tool or refuse, so it cannot answer before looking anything up.
2. A second call fills that tool's arguments under its JSON schema. Id parameters are restricted to ids that already
   appeared in tool results, so the model cannot invent one.
3. Repeating an identical call ends the step loop.

This works with models that have no tool support at all. `native` uses Ollama's tool calling; it suits models
trained for it (qwen2.5, llama3.1) and is unreliable with mistral 7B, which stops calling tools once it is offered
more than a few.
