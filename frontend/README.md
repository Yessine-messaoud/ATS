# ATS frontend (Next.js 16)

Recruiter interface: jobs and requirement validation, CV upload and evidence review, explainable ranking,
pipeline board.

## Architecture

- **Backend-for-frontend.** Pages are Server Components that call the FastAPI backend from the server
  (`src/lib/api.ts`). Mutations are Server Actions (`src/app/actions.ts`). The browser never talks to the backend:
  no CORS, and `API_URL` is a server-only variable.
- **Always live data.** Reads call `connection()`, so pages render at request time and `next build` never contacts
  the backend.
- **Typed against the API.** `src/lib/api-types.ts` is generated from the backend's OpenAPI schema. CI fails if it is
  out of date. After changing a backend endpoint, run:

  ```bash
  npm run gen:api
  ```

- The original uploaded CV is streamed through `/candidates/[id]/file`, served with a `sandbox` CSP.

## Pages

| Route | Purpose |
|---|---|
| `/jobs` | Job list. Paste a job description to create a job. |
| `/jobs/[id]` | Ranking. Candidates meeting the mandatory criteria first, the others listed separately; blind screening toggle; add to pipeline; score details. |
| `/jobs/[id]/requirements` | Review and validate the extracted requirements (required/preferred, levels, evidence). |
| `/jobs/[id]/pipeline` | Kanban board (drag-and-drop or menu). Each move is logged as a recruiter decision. |
| `/jobs/[id]/weights` | Per-job scoring weights, missing-skill penalty, knock-outs on/off. |
| `/candidates` | Candidate list with review flags; multi-file CV upload. |
| `/candidates/[id]` | Profile review: each item next to its evidence; confirm or remove unverified items; source document and security flags; best matching jobs. |
| `/matches/[id]` | Score breakdown, mandatory criteria, explanation (fact-checked), interview questions. |

## Development

```bash
cp .env.example .env.local    # API_URL=http://localhost:8000
npm install
npm run dev                   # http://localhost:3000
npm run lint && npx next typegen && npm run typecheck
```

For demo data without an LLM key, run `uv run python -m scripts.seed_demo` in `backend/`.
