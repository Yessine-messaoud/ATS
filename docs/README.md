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

To run the whole backend in Docker instead: `docker compose up -d --build`.

## Development

```bash
cd backend
uv run pytest                # DB tests are skipped if Postgres is not running
uv run ruff check . && uv run ruff format .
uv run mypy app tests examples migrations/env.py
uv run alembic revision --autogenerate -m "describe change"   # after changing app/db/records.py

# Optional: run the same checks on every commit
uv run pre-commit install --config ../.pre-commit-config.yaml
```
