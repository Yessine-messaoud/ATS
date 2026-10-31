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

## Interface (RecruitAI design)

- **Layout.** Navy sidebar (Dashboard, Jobs, Candidates, AI Assistant, CV Evaluation, Analytics, Audit Log,
  Settings) with the recruiter profile at the bottom. The top bar has global search (**Ctrl+K / ⌘K**),
  notifications, a theme switcher (light, dark or system, remembered per browser) and the profile menu. Brand tokens
  (`brand`, `navy`, `lavender`, `canvas`) are defined in `app/globals.css`.
- **Real data only.** Every number comes from the API. Some data does not exist in the backend yet, and is labelled
  rather than invented:
  - *Draft* job status: the backend only has open or closed jobs, plus validated or not.
  - Company logos: not stored, so the company initial is shown.
  - Recruiter accounts: single-user mode for now.
  - Free-form comments: notes are recorded with each stage decision instead.
  Analytics can preview illustrative figures on request (`?sample=1`). Every chart is then badged **Sample data** and
  a banner explains it.
- **Scores and AI, kept apart.** The evaluation page separates three layers:
  - the deterministic **scoring engine** (score ring, criteria bars, skills coverage);
  - the **AI-generated** summary (lavender panel, labelled, fact-checked against the factors);
  - the **recruiter decision** (stage plus note, written to the audit log). Only this changes the pipeline; the AI
    never rejects or advances a candidate.
- **Charts.** Recharts Client Components receive pre-aggregated, non-personal series computed on the server
  (`lib/analytics.ts`).
- **Primitives.** Shared building blocks live in `components/ui.tsx` (server-safe) and
  `components/interactive.tsx` (dropdown menu, native `<dialog>`, slider, sortable header, pagination).
  Conflicting Tailwind classes are merged with `tailwind-merge`.
- **Accessibility.** Visible focus everywhere, a skip link, ARIA roles on menus, dialogs, tabs, sliders and sort
  headers, keyboard navigation in the palette and menus, and responsive layouts down to 375 px.

## Pages

| Route | Purpose |
|---|---|
| `/` | Dashboard: active jobs, applications, shortlisted, pending evaluations; applications trend; pipeline donut; open jobs; to-do queue; activity. |
| `/jobs` | Jobs table: search, status and contract filters, sorting, pagination, row actions. "Create job" opens step 1 (paste the description; the AI extracts the requirements). |
| `/jobs/[id]/requirements` | Steps 2–3: review and edit the extracted requirements (required/preferred skills, minimum-experience slider, education level, location, contract), with live validation, then **Validate & publish**. |
| `/jobs/[id]` · `/pipeline` · `/weights` | Ranking, Kanban pipeline, scoring weights. |
| `/candidates` | Candidates table: applied position, experience, skills, date, evaluation status, best match score; filters by job, skill, minimum experience, status and minimum score; upload dialog. |
| `/candidates/[id]` | Tabs: Evaluation (scores per open job), Profile review (evidence), CV (PDF preview, security flags), Privacy. |
| `/evaluations` | CV evaluation queue (applications in New or Screening), recent evaluations, profiles to verify. |
| `/matches/[id]` | CV evaluation: score, coverage, strengths and gaps, AI summary, CV preview, recruiter decision and history. |
| `/analytics` | Six charts with 7, 30 or 90-day and custom date ranges: applications over time, pipeline, funnel, top skills, applications per job, score distribution. |
| `/assistant` | Chat with the recruitment assistant (actions need confirmation). |
| `/audit`, `/settings`, `/privacy` | Audit log; preferences and read-only configuration; candidate notice. |

## Development

```bash
cp .env.example .env.local    # API_URL=http://localhost:8000
npm install
npm run dev                   # http://localhost:3000
npm run lint && npx next typegen && npm run typecheck
```

For demo data without an LLM key, run `uv run python -m scripts.seed_demo` in `backend/`.
