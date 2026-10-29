# TODO — AI Recruitment & Job Matching Agent

Phases follow `description.txt` §16. Findings referenced as (A§x) come from `docs/AUDIT.md`.
A phase is complete when its **Done when** line is true.

## Phase 0 — Foundations

- [ ] `git init`, first commit, push to GitHub
- [ ] Fix `.gitignore`: add `!.env.example` (A§3.1-3)
- [ ] Create a Python 3.12 environment with `uv`. Replace `requirements.txt` with `pyproject.toml` + `uv.lock` and raise the pins (pydantic ≥ 2.11) (A§3.1-1)
- [ ] Add ruff + mypy + pytest config and pre-commit hooks
- [ ] `app/config.py` with `pydantic-settings`. Compose reads its credentials from `.env` (A§3.1-4)
- [ ] Remove `version:` from `docker-compose.yml`, switch the image to `pgvector/pgvector:pg16`, and add a backend Dockerfile and service
- [ ] Fix the quick start in `docs/README.md` (`cd ..` is the wrong directory)
- [ ] GitHub Actions: lint, type-check and tests on every PR
- [ ] **Models v2** (A§3.2):
  - [ ] Replace the 11 skill buckets with `skills: list[Skill]` + `category`
  - [ ] Add a `LanguageLevel` CEFR enum (A1–C2, native) and use it for both candidate and job
  - [ ] Split `ProficiencyLevel` (skills) from language levels
  - [ ] Add `confidence` and `verified` to extracted items
  - [ ] Add `id`, `created_at`, `schema_version`, and move `raw_text` out of the profile
  - [ ] Validators: `min_length=1` on names, finite floats (reject `inf`), ISO 4217 upper-case currency, URL validation (reuse `UrlModel`), check `duration_months` against dates
  - [ ] Remove the duplicate job fields (`travel`/`travel_requirements`, `country`) and separate contract type from schedule
  - [ ] Remove unused imports
  - [ ] Write tests for every probe in A§3.2
- [ ] SQLAlchemy models (Candidate, Job, Application, Match, Document, AuditLog) + first Alembic migration

**Done when:** a fresh clone works with `uv sync && pytest && docker compose up` and CI is green.

## Phase 1 — Extraction

- [ ] Upload endpoint with MIME check on file bytes, size and page limits, and temp file cleanup
- [ ] PDF text extraction (PyMuPDF), plus detection of invisible text (colour, size, off-page)
- [ ] OCR fallback (Tesseract) when the extracted text is too short
- [ ] Section detector (experience, education, skills…) for FR and EN
- [ ] `LLMClient` interface + one provider, with structured output from the Pydantic JSON schema
- [ ] Repair loop: send validation errors back to the LLM (2 retries max)
- [ ] Partial validation: null out the invalid field and keep the rest of the profile
- [ ] **Evidence verifier:** fuzzy-match each `evidence` against the source text and set `verified`
- [ ] Job description → `JobProfile` extraction
- [ ] Email ingestion: parse MIME and route attachments through the same pipeline
- [ ] Log the model, prompt version, tokens, cost and latency for each extraction
- [ ] **Gold set v0:** 15 CVs + 5 jobs annotated by hand (JSON) in `eval/data/`
- [ ] `eval/extraction.py`: per-field P/R/F1 and hallucination rate, results written to `eval/results/`

**Done when:** skill extraction F1 is measured and reported on the gold set, and hallucination rate is measured.

## Phase 2 — Matching & explanation

- [ ] Simple skill normalizer v0 (synonym dictionary + fuzzy match). ESCO comes in Phase 4
- [ ] Knock-out filters: work authorization, mandatory language, certification, location
- [ ] Per-dimension scorers in pure functions, each one unit-tested
- [ ] Skill strength from recency, duration and number of evidence items
- [ ] Penalty for each missing required skill
- [ ] Per-job configurable weights
- [ ] `MatchResult` with all factors, persisted with the engine version
- [ ] `GET /api/jobs/{id}/ranking`: rank candidates for a job
- [ ] LLM explanation generated **only from the factors**, plus interview questions for gaps
- [ ] Faithfulness check: every claim in the explanation must map to a factor
- [ ] Gold set: candidate×job relevance labels (0–3)
- [ ] `eval/matching.py`: NDCG@10, Spearman correlation vs human ranking

**Done when:** a job ranks the pool with explanations, and NDCG@10 is reported.

## Phase 3 — ATS UI (Next.js)

- [ ] Replace the template page and metadata. Install shadcn/ui. Generate a typed API client from the OpenAPI schema
- [ ] Jobs list + create a job (paste text → review and edit the requirement grid)
- [ ] Candidate upload (drag & drop, several files) with extraction status
- [ ] Profile review screen: extracted fields next to their evidence, unverified items highlighted, editable
- [ ] Ranking view per job: score breakdown, knocked-out candidates in a separate tab
- [ ] Kanban pipeline with stages. Every move is a logged human decision
- [ ] Blind screening toggle
- [ ] Recruiter corrections saved as feedback data

**Done when:** a recruiter can go from a job description and 10 PDFs to a ranked shortlist and a Kanban pipeline.

## Phase 4 — Semantic search & taxonomy

- [ ] Import ESCO skills (FR/EN). Map the normalizer onto ESCO IDs
- [ ] Skill graph (implies / parent / related) with partial-match weights
- [ ] Multilingual embeddings stored in pgvector (profiles, jobs, experiences)
- [ ] Hybrid retrieval (Postgres full-text + vector) → top-K → deterministic score
- [ ] Optional cross-encoder rerank, kept only if NDCG improves
- [ ] Candidate → job recommendations + talent rediscovery when a new job opens
- [ ] Candidate deduplication (exact + fuzzy, human-confirmed merge)

**Done when:** NDCG@10 improves over the Phase 2 baseline on the gold set.

## Phase 5 — Agent

- [ ] Tool definitions for the existing services (parse, match, search, explain, draft_email, interview_questions)
- [ ] Agent loop with tool calling, and confirmation required before side-effecting actions
- [ ] `POST /api/agent/chat` + chat panel in the UI
- [ ] Agent eval set (≈30 requests with expected tool sequences): tool selection accuracy, completion rate, cost, latency

**Done when:** the agent eval is reported, and the agent never computes a score itself.

## Phase 6 — Fairness, security, discovery

- [ ] Counterfactual bias tests in CI (name and gender swap → score delta must be 0)
- [ ] Adversarial set: prompt-injection CVs, hidden text, bad scans → score unchanged and file flagged
- [ ] Selection-rate monitoring (4/5 rule) on feedback data
- [ ] Encryption at rest for documents, PII-free logs, retention purge job, candidate export and delete endpoints
- [ ] Audit log viewer
- [ ] External job sources through official APIs only (e.g. Adzuna), with the same parse, dedup and match pipeline
- [ ] Candidate space: gap analysis + CV advice
- [ ] Transparency notice and "request human review" flow for candidates

**Done when:** the bias and injection suites run in CI, and the GDPR export and delete flows work end to end.

## Ongoing

- [ ] Keep `docs/` in sync: architecture diagram, model docs, eval results per phase
- [ ] Track LLM cost per CV and keep it under a budget
- [ ] Demo dataset + seed script for presentations
