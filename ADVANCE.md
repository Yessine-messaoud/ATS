# Project status: RecruitAI (AI recruitment & ATS)

_Last updated: 31 October 2026 · repository `github.com/Yessine-messaoud/ATS`_

## Summary

Phases 0–6 and the interface redesign are **merged into `main`** (tagged `v1.0-rc1`; the original project is tagged
`v0-baseline`). Phase 7, accounts, roles and portals, is on branch `phase-7-portals`, to merge next.

RecruitAI is now a multi-company platform with three kinds of users:

| Role | What they get |
|---|---|
| **Platform admin** | Overview, approve or suspend companies, staff accounts, password resets, CV processing queue, full audit log |
| **Recruiter** (a company) | The ATS, limited to their own company: jobs, candidates, rankings, assistant, analytics, activity log, company profile, team |
| **Candidate** | Public job board, apply with a CV, follow each application's status (never scores), own profile, consent, data export, account deletion |

| | |
|---|---|
| Progress | Phases 0–7 built. 104 TODO items done, 26 open (extensions, see below). |
| Backend tests | 235 passing (pytest), plus ruff, strict mypy and Alembic drift checks, all in CI |
| Frontend | Lint, typecheck and production build pass; all three roles checked end to end in a browser, desktop and 375 px |
| AI | Runs locally on the GPU (Ollama + mistral 7B, $0) or on Claude with an API key |
| Security | Documents encrypted at rest (key set locally), Next.js 16.4.1 (critical advisories fixed) |

## Branches

| Branch | Content | Status |
|---|---|---|
| `main` | Phases 0–6 + RecruitAI interface | Merged, tag `v1.0-rc1` |
| `phase-7-portals` | Accounts and sessions, roles, company isolation, admin console, recruiter and company profiles, job board, candidate portal, background CV reading | Pushed; to merge |

## Measured quality (latest evaluation runs)

| Area | Result | Caveat |
|---|---|---|
| CV extraction (local mistral) | Skills F1 0.92 · required skills F1 1.0 · languages F1 0.98 · items not found in the CV 4% · sensitive data leaks 0 · ~70 s per CV | Only 9 documents (6 CVs, 3 job ads) |
| Matching | NDCG@3 0.97 · Spearman 0.82 | Only 18 job–candidate pairs, labelled by the developer, not by recruiters |
| Search | Recall@10 1.0 (hybrid) vs 0.89 (vector only) | Placeholder embeddings, few queries |
| Assistant (local mistral, 30 requests) | 12/30 passed · tool selection 0.47 · forbidden actions 0 · fairness requests refused 4/4 | Limited by the 7B model |
| Fairness and security | Names, gendered titles and personal characteristics leave scores unchanged; hidden text and prompt injection are flagged (tested in CI) | Not a full fairness assessment |

## External review (ChatGPT, `docs/eval.md`), checked against the code

- **Confirmed:** small evaluation sets (numbers above), weak assistant, placeholder embeddings, no accounts (now done), unmerged branches (now done).
- **Already in place:** skill-gap analysis (coverage, missing vs unverified), per-job scoring weights.
- **Doable next:** qwen2.5:7b comparison, neural embeddings via Ollama, extraction timing split (text vs AI), ranking stability test, proxy-variable fairness tests, French interface, recruitment metrics (time-to-hire from the audit log), Playwright in CI.
- **Needs people or accounts:** a 100–200 CV benchmark (manual annotation), recruiter-validated labels, a pilot, demographic fairness on real data, Claude comparison (API key), job-board integrations, legal EU AI Act assessment.

## What works today

- **Job board:** visitors browse open jobs of approved companies, search and filter, read the job and company profile.
- **Candidates:** sign up, apply with a CV (read in the background in about a minute), follow status from Received to
  Offer or Not selected, withdraw, correct their profile (changes can never raise a score), send a new CV, choose
  whether all companies can find them, download their data, delete their account.
- **Recruiters:** everything from Phases 1–6 (job extraction and validation, CV evidence check, explainable ranking,
  pipeline, assistant, analytics), limited to their company; job-board applicants arrive in the pipeline tagged
  "Job board"; company profile and team.
- **Admins:** approve, suspend or reinstate companies (suspension signs recruiters out and hides jobs), create staff
  accounts with one-time passwords, deactivate accounts, follow the CV queue and the full audit log.
- **Privacy:** encryption at rest, retention purge, export and erasure, consent, per-company audit log.

## Known limitations

- **Assistant quality on the local model.** mistral 7B often stops after one lookup.
- **Recruiter CV uploads still wait for the AI** (about a minute); job-board CVs already use the background queue.
- **No email yet:** no sign-up confirmation, password reset by email or status notifications (needs an SMTP provider).
  Admins reset passwords and hand over one-time passwords.
- **English interface only.**
- **Small demo dataset** and placeholder search embeddings.

## Open actions

**Owner decisions / quick wins**
1. Review and merge `phase-7-portals` into `main`.
2. Create the first admin on each environment: `uv run python -m scripts.create_user --role admin ...` (see `docs/README.md`).
3. Back up `DOCUMENT_ENCRYPTION_KEYS` (set in `backend/.env` and `.env`): losing it makes stored CVs unreadable.
4. Rebuild the Docker images (`docker compose up -d --build`): the running containers still have the pre-Phase-7 code.
5. Dismiss the old GitHub "generic password" alert (placeholder removed; still in history).

**Next development candidates**
- Email provider: confirmation, password reset, status notifications to candidates.
- `qwen2.5:7b` assistant comparison; neural embeddings (`nomic-embed-text`).
- Background queue for recruiter uploads too.
- French interface.
- Recruitment metrics (time-to-hire, conversion per stage) from the audit log.
- Playwright role checks in CI.

## Where to look

| Document | Content |
|---|---|
| `TODO.md` | Detailed checklist per phase |
| `description.txt` | Product description (v2) |
| `docs/README.md` | Setup, accounts and roles, API, privacy and security operations |
| `backend/eval/README.md` | How the evaluations work, results history |
| `frontend/README.md` | Interface structure and pages |
