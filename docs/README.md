# ATS Project

## Project structure

- `backend/` : FastAPI application
- `frontend/` : Next.js application
- `infra/` : infrastructure config and deployment assets
- `docker-compose.yml` : local Postgres and Redis services

## Quick start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or .venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Infrastructure

```bash
cd ..
docker compose up -d
```
