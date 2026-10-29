# ATS Project

AI recruitment and job matching platform. See [`description.txt`](../description.txt) for the vision,
[`TODO.md`](../TODO.md) for the roadmap and [`AUDIT.md`](AUDIT.md) for the initial audit.

## Project structure

- `backend/`: FastAPI application (Python 3.12, managed with [uv](https://docs.astral.sh/uv/))
  - `app/models/`: canonical Pydantic profiles (also used as the LLM structured-output schema)
  - `app/db/`: SQLAlchemy records
  - `migrations/`: Alembic migrations
- `frontend/`: Next.js application
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

To run the whole backend in Docker instead: `docker compose up -d --build`. The image includes Tesseract, so OCR
for scanned CVs works there. Locally, OCR is skipped (and flagged) unless Tesseract is installed.

### Claude API key (CV and job extraction)

Extraction calls `claude-opus-5-5`. Set `ANTHROPIC_API_KEY` in `.env` (for Docker) or `backend/.env` (for a local
backend), or run `ant auth login`. Without credentials, the API still runs: extraction endpoints return `503`, and
the tests use a scripted fake LLM.

## API (Phase 1)

| Endpoint | Purpose |
|---|---|
| `POST /api/candidates/upload` | Upload a CV (PDF, DOCX or text) or an application email (`.eml`). Returns the extracted profile with evidence checks and document flags (hidden text, possible prompt injection, OCR). |
| `GET /api/candidates`, `GET /api/candidates/{id}` | List or read candidates. |
| `POST /api/jobs` | `{"text": "<job description>"}` → extracted requirement grid (not yet validated). |
| `PUT /api/jobs/{id}/requirements` | Recruiter-validated `JobProfile`; marks the grid as the matching reference. |
| `GET /api/jobs`, `GET /api/jobs/{id}` | List or read jobs. |

Interactive docs: http://localhost:8000/docs. Extraction quality is measured with the harness in
[`backend/eval/`](../backend/eval/README.md).

## Development

```bash
cd backend
uv run pytest                # DB tests are skipped if Postgres is not running
uv run ruff check . && uv run ruff format .
uv run mypy app tests examples eval migrations/env.py
uv run alembic revision --autogenerate -m "describe change"   # after changing app/db/records.py

# Optional: run the same checks on every commit
uv run pre-commit install --config ../.pre-commit-config.yaml
```
