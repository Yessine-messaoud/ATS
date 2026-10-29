# TODO — AI Recruitment & Job Matching Agent

Phases follow `description.txt` §16. Findings referenced as (A§x) come from `docs/AUDIT.md`.
A phase is complete when its **Done when** line is true.

## Phase 0 — Foundations

- [x] `git init` + baseline commit
- [ ] Create the GitHub repo and push (needs a remote — owner decision)
- [x] Fix `.gitignore`: add `!.env.example` (A§3.1-3)
- [x] Create a Python 3.12 environment with `uv`. Replace `requirements.txt` with `pyproject.toml` + `uv.lock` and raise the pins (pydantic ≥ 2.11) (A§3.1-1)
- [x] Add ruff + mypy + pytest config and pre-commit hooks
- [x] `app/config.py` with `pydantic-settings`. Compose reads its credentials from `.env` (A§3.1-4)
- [x] Remove `version:` from `docker-compose.yml`, switch the image to `pgvector/pgvector:pg16`, and add a backend Dockerfile and service
- [x] Fix the quick start in `docs/README.md` (`cd ..` is the wrong directory)
- [x] GitHub Actions: lint, type-check and tests on every PR
- [x] **Models v2** (A§3.2):
  - [x] Replace the 11 skill buckets with `skills: list[Skill]` + `category`
  - [x] Add a `LanguageLevel` CEFR enum (A1–C2, native) and use it for both candidate and job
  - [x] Split `ProficiencyLevel` (skills) from language levels
  - [x] Add `confidence` and `verified` to extracted items
  - [x] `schema_version` on profiles; `id`/timestamps on DB records (profiles are the LLM schema); `raw_text` moved to `DocumentRecord`
  - [x] Validators: `min_length=1` on names, finite floats (reject `inf`), ISO 4217 upper-case currency, URL validation (reuse `UrlModel`), check `duration_months` against dates
  - [x] Remove the duplicate job fields (`travel`/`travel_requirements`, `country`) and separate contract type from schedule
  - [x] Remove unused imports
  - [x] Write tests for every probe in A§3.2
- [x] SQLAlchemy models (Candidate, Job, Application, Match, Document, AuditLog) + first Alembic migration

**Done when:** a fresh clone works with `uv sync && pytest && docker compose up` and CI is green.

## Phase 1 — Extraction

- [x] Upload endpoint with MIME check on file bytes, size and page limits (files are processed in memory, so there are no temp files to clean up)
- [x] PDF text extraction (PyMuPDF), plus detection of invisible text (white, tiny, transparent, off-page)
- [x] OCR fallback (Tesseract) when the extracted text is too short. Tesseract is installed in the Docker image; locally the document is flagged `ocr_unavailable` instead
- [x] Section detector (experience, education, skills…) for FR and EN
- [x] `LLMClient` interface + Claude provider (`claude-opus-5-5`). The tool schema is generated from the Pydantic model. Not `strict`: the profiles exceed the strict-schema limits, so Pydantic validates instead
- [x] Repair loop: validation errors are sent back as an error `tool_result` (2 retries max)
- [x] Partial validation: drop the invalid field or list item and keep the rest of the profile
- [x] **Evidence verifier:** fuzzy-match each `evidence` (or the item name) against the source text and set `verified`
- [x] Job description → `JobProfile` extraction, plus `PUT /api/jobs/{id}/requirements` for recruiter validation
- [x] Email ingestion: parse MIME and route PDF/DOCX attachments through the same pipeline
- [x] Log the model, prompt version, tokens, latency and request IDs for each extraction (`extraction_meta`), plus an audit log entry
- [x] Prompt-injection screening (regex FR/EN on visible and hidden text) and document flags shown to the recruiter
- [x] Duplicate detection by SHA-256 (409 with the existing record id)
- [x] **Gold set v0:** 6 CVs (3 EN, 3 FR, including 1 adversarial) + 3 jobs in `eval/data/`
- [ ] Grow the gold set to 15 CVs + 5 jobs, including real anonymised CVs (with consent) and two-column layouts
- [x] `eval/run_extraction.py`: per-field P/R/F1, unverified (hallucination) rate, sensitive leaks, security flags, cost and latency, written to `eval/results/`
- [ ] **Run the eval with an API key** and commit the first results file
- [ ] Move extraction to a background task (uploads currently block while the LLM call runs)

**Done when:** skill extraction F1 is measured and reported on the gold set, and hallucination rate is measured.

## Phase 2 — Matching & explanation

- [x] Skill normalizer v0: synonyms, implication graph (PostgreSQL ⟹ SQL, transitive), related-skill partial credit, strict fuzzy matching. ESCO comes in Phase 4
- [x] Knock-out filters: mandatory language (CEFR), certification, location/relocation, work authorization (always left to the recruiter). Missing information gives `unknown`, never `fail`
- [x] Per-dimension scorers as pure functions, each unit-tested (required/preferred skills, experience, seniority, languages, education with experience equivalence, location/work mode)
- [x] Skill strength from professional use (duration), projects, bare listing, and recency; skills mentioned only in experience text are found too. Unverified claims earn no credit
- [x] Multiplicative penalty for each missing required skill (8% by default)
- [x] Per-job configurable weights (`PUT /api/jobs/{id}/weights`), normalized over the dimensions that apply
- [x] `MatchResult` with every factor (stable ids), persisted with the engine version (`POST /api/matches`) plus an audit entry
- [x] `GET /api/jobs/{id}/ranking`: candidates passing knock-outs, then knocked-out ones listed separately; `blind=true` hides names
- [x] `GET /api/candidates/{id}/recommendations`: open jobs ranked for a candidate
- [x] LLM explanation built **only from the factors** (no CV text or personal data), plus interview questions; deterministic template fallback
- [x] Faithfulness check: claims citing unknown factors, the wrong polarity or numbers absent from the factors are dropped and reported
- [x] Counterfactual test: name, email, phone and links do not change the result
- [x] Gold set: 18 candidate×job relevance labels (0–3), written before the engine; matching fixtures in `eval/data/matching/`
- [x] `eval/run_matching.py`: NDCG@3, NDCG@all, Spearman, top-1 accuracy; regression-guarded in CI. Baseline `match-v1`: NDCG@3 0.972, Spearman 0.816, top-1 3/3
- [ ] Grow the matching gold set (more jobs and candidates, a second annotator for inter-rater agreement)
- [ ] Experience relevance is skill-based only; add domain/title similarity (e.g. BI analyst ≠ data engineer despite SQL)
- [ ] Measure LLM explanation faithfulness (dropped-claim rate) once an API key is available

**Done when:** a job ranks the pool with explanations, and NDCG@10 is reported. *(Done: NDCG@3 and NDCG@all are reported, since the pool has only 6 candidates.)*

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
