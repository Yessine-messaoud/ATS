# TODO — AI Recruitment & Job Matching Agent

Phases follow `description.txt` §16. Findings referenced as (A§x) come from `docs/AUDIT.md`.
A phase is complete when its **Done when** line is true.

## Phase 0 — Foundations

- [x] `git init` + baseline commit
- [x] Create the GitHub repo and push (needs a remote — owner decision)
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
- [x] **First eval runs** on the local model (mistral 7B, GPU, $0): skills F1 0.917, required skills 1.0, languages 0.978, experiences 0.842, unverified evidence 4.0%, sensitive leaks 0 (1 before the protected-attribute pass), ~69 s per document. Weakest: preferred skills (recall 0.30). Claude run still to do when a key is available
- [ ] Move recruiter uploads to the background queue too (job-board CVs already use it, Phase 7)

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

- [x] Replaced the template page and metadata. Typed API client generated from the OpenAPI schema (`npm run gen:api`), with a CI drift check. shadcn/ui not added (its CLI fetches code from an external registry); small Tailwind primitives in `components/ui.tsx` instead
- [x] Backend-for-frontend: Server Components and Server Actions call FastAPI from the server; reads use `connection()` (request-time rendering, build never needs the backend)
- [x] Jobs list + create a job (paste text → review and edit the requirement grid → validate)
- [x] Candidate upload (drag & drop, several files, uploaded one at a time) with per-file status and flags
- [x] Profile review screen: each item next to its evidence; unverified items highlighted; recruiter can confirm or remove them, edit title, seniority and language levels; source document text, hidden text and injection warnings; original file viewer (sandboxed)
- [x] Ranking view per job: score bars, matched/missing required skills, knocked-out candidates in a separate section with reasons
- [x] Match detail page: dimensions, factors, knock-outs, explanation with dropped claims, interview questions
- [x] Kanban pipeline with stages (drag-and-drop + keyboard-accessible menu, optimistic updates). Every move is a logged human decision (`application.stage_changed`)
- [x] Blind screening toggle (ranking and pipeline; names replaced by `Candidate xxxxxxxx`, verified absent from the HTML)
- [x] Recruiter corrections saved as feedback data: the first extraction is kept in `extracted_profile`, and the audit log records changed paths only (no personal data)
- [x] Per-job weights page; job open/closed status
- [x] Demo seed script (`scripts/seed_demo.py`, idempotent, no LLM); frontend Docker image; `docker compose up` runs the full stack
- [x] Authentication and per-recruiter audit actor (currently `recruiter`)
- [ ] Browser end-to-end tests (Playwright) for the interactive flows: upload, save review, drag-and-drop
- [ ] Highlight evidence quotes inside the source document text
- [ ] Interface in French as well as English (i18n)

**Done when:** a recruiter can go from a job description and 10 PDFs to a ranked shortlist and a Kanban pipeline. *(Done, except that creating jobs and uploading CVs need an `ANTHROPIC_API_KEY`; the demo seed covers the rest without one.)*

## Phase 4 — Semantic search & taxonomy

- [x] ESCO importer for the official CSV export (`skills_en.csv`, `skills_fr.csv`, `broaderRelationsSkillPillar.csv`) → `taxonomy_skills` / `taxonomy_broader`, loaded at API startup (`scripts/import_esco.py`)
- [x] Normalizer uses ESCO when loaded: FR/EN preferred and alternative labels → one canonical skill; narrower ⟹ broader implication. The engine version records the taxonomy (`match-v1+esco-x.y`)
- [ ] **Run the import with the real ESCO download** (manual download from esco.ec.europa.eu; tested only on a fixture in the ESCO CSV layout)
- [x] Skill graph with partial-match weights (curated v0, kept alongside ESCO)
- [x] Embeddings in pgvector (`candidate_search` / `job_search`, HNSW cosine index) + Postgres full-text (`tsvector`, GIN), kept in sync on upload, correction and job changes; `scripts/reindex.py`
- [x] Embedding provider interface; default `HashingEmbedder` (deterministic character n-grams, no download or key)
- [ ] Plug in a neural multilingual embedding model (provider choice pending) and compare on the retrieval eval
- [x] Hybrid retrieval (vector + full-text, Reciprocal Rank Fusion) → shortlist → deterministic score, used automatically above `FULL_SCORING_LIMIT` (500) candidates; the ranking reports its mode
- [x] Retrieval eval with 300 synthetic distractors: hybrid recall@10 = 1.0 (vector-only 0.889), regression-guarded
- [ ] Cross-encoder rerank: skipped. Final ordering is the deterministic score, so a reranker would only change the shortlist, and recall@10 is already 1.0
- [x] Candidate → job recommendations (Phase 2) + talent rediscovery: rankings always cover the whole pool (or its hybrid shortlist), including past applicants
- [x] Duplicate detection (email, phone, similar name + near-identical profile), flagged at upload; recruiter-confirmed merge moves applications and match history (UI + audit)
- [x] Talent-pool consent: only rediscover candidates who agreed (needs a consent field; see Phase 6)

**Done when:** NDCG@10 improves over the Phase 2 baseline on the gold set. *(Not applicable as written: retrieval does not change the order, which is always the deterministic score. Measured instead: retrieval recall@K on a 306-candidate pool.)*

## Phase 5 — Agent

- [x] 11 tools over the existing services: list_jobs, search_candidates (hybrid search), get_candidate, get_job, rank_candidates_for_job, explain_match, interview_questions, recommend_jobs_for_candidate, get_pipeline, and two actions (add_candidate_to_pipeline, move_application_stage). Tool outputs never include contact details or raw CV text, and honour blind mode
- [x] Agent loop with tool calling (`claude-opus-5-5`, `tool_choice: auto`, refusal fallback, prompt caching). Manual loop (not the SDK tool runner) because a turn pauses across HTTP requests for confirmation; history stored as JSON and replayed unchanged (thinking blocks included)
- [x] Confirmation before side effects: actions are proposed, never executed by the model; the recruiter approves or declines each one; a new message declines pending actions; executed actions are saved before the model is called again (no double execution); audit actor `recruiter (via assistant)`
- [x] Robustness: invalid inputs and unknown tools come back as `is_error` results; cut-off calls get error results; step limit (10); no state saved when the model call fails
- [x] System prompt: scores only from the engine, facts only from tool results, refuse filtering on protected characteristics, CV content treated as data, emails drafted but never sent
- [x] `POST /api/agent/conversations`, `/messages`, `/decisions`; chat page with approve/decline cards and blind mode
- [x] Agent eval set: 30 requests (EN/FR: lookup, search, ranking, explanation, comparison, recommendation, interview, pipeline, actions, emails, fairness, privacy, robustness) with must-call / must-not-call tools and expected confirmations; `eval/run_agent.py` measures completion, tool-selection accuracy, forbidden-tool rate, confirmation-gating accuracy, model calls, latency and cost, and saves replies for manual review. The grading is unit-tested with a scripted model
- [x] **Agent eval on the local model** (mistral 7B): 12/30 passed, completion 100%, tool selection 0.47, forbidden tools 0, confirmation gating 0.83, fairness 4/4, ~21 s per request (native tool calling: 6/30, tool selection 0.30). Failures: it stops after one lookup and never proposes pipeline actions. Replies of fairness and email cases still need a human read
- [ ] Agent eval with Claude, and with qwen2.5:7b, for comparison
- [ ] Stream replies to the UI (currently the full turn is returned at once)
- [x] Render Markdown (tables) in assistant replies

**Done when:** the agent eval is reported, and the agent never computes a score itself. *(Harness ready and tested; the run needs an API key. The second part holds by construction: no tool lets the model set a score.)*

## Local LLM (Ollama)

- [x] `LLM_PROVIDER=ollama` (default) or `anthropic`; extraction through structured outputs (JSON schema `format`, every top-level key required); assistant through an adapter that keeps the stored Anthropic-format history
- [x] GPU: `num_gpu=99` puts mistral 7B fully on a 6 GB RTX 3050 at an 8k context (38 tok/s, vs 22 with Ollama's default CPU/GPU split); output capped per call (`num_predict`) so a repeating model cannot run for minutes
- [x] Structured tool mode for the assistant: enum-constrained routing, schema-constrained arguments, ids restricted to ids seen in tool results, no answer before a lookup, loop guard (mistral 7B called no tool natively with 11 tools offered)
- [ ] Try `qwen2.5:7b` (strong at tool calling, fits 6 GB) in `native` and `structured` modes and compare on the agent eval
- [ ] Neural embeddings through Ollama (`nomic-embed-text`) to replace the hashing embedder; compare recall@K

## Phase 6 — Fairness, security, discovery

- [x] Counterfactual bias tests in CI: 8 names from several origins, gendered French titles, protected mentions in free text, ranking invariance, schema has no protected fields; dedicated CI step
- [x] Adversarial set through the upload API: white/tiny/off-page text, keyword stuffing, EN/FR prompt injection, blank scan → file flagged, planted skills unverified, score equal to the clean CV. The suite found two detector misses, now fixed, and false positives are tested
- [x] Protected characteristics removed from extracted profiles by a deterministic pass (the local model kept a marital status in the first eval run); assistant policy guard refuses protected-characteristic requests before any model call
- [ ] Selection-rate monitoring (4/5 rule): needs voluntary, separately stored equal-opportunity data, which the system deliberately does not collect yet
- [x] Encryption at rest (Fernet, key rotation, migration script; production refuses to start without a key), PII-masking log filter, retention job (`scripts.retention`), candidate export and erasure endpoints
- [x] Talent-pool consent field; `REQUIRE_TALENT_POOL_CONSENT` restricts rankings, search and recommendations
- [x] Audit log API and viewer (`/audit`)
- [x] Transparency notice for candidates (`/privacy`), built from the live configuration
- [ ] "Request human review" flow for candidates (needs the candidate space)
- [ ] External job sources through official APIs only (e.g. Adzuna), with the same parse, dedup and match pipeline
- [ ] Candidate space: gap analysis + CV advice
- [x] Authentication and roles (recruiter, admin, DPO); until then audit actors are generic ("recruiter")

**Done when:** the bias and injection suites run in CI, and the GDPR export and delete flows work end to end. *(Done: both suites run as a CI step; export and erasure are tested end to end through the API and available in the UI.)*

## Phase 7 — Accounts, roles and portals

- [x] Users, companies and sign-in sessions (scrypt passwords, hashed opaque tokens, httpOnly cookie, login throttling)
- [x] Roles: platform admin, company recruiter, candidate; every route checks the role
- [x] Company isolation: jobs, candidates, rankings, assistant tools, search, duplicates and audit log scoped per company (404 outside)
- [x] Audit log names the real actor (`user:<id>`) and is filtered per company
- [x] Admin console: overview, approve/suspend companies, create staff accounts, deactivate, reset passwords, CV queue
- [x] Recruiter profile, company profile shown on the job board, team management
- [x] Public job board (open jobs of approved companies) with search and filters
- [x] Candidate portal: sign up, apply with a CV, follow status (never scores), withdraw, correct own profile, replace CV, consent, export, delete account
- [x] Candidate self-edits can never raise a score (added or changed items are unverified)
- [x] Background CV reading for job-board applications (database queue, worker thread, retries)
- [x] Migration with backfill of existing data; 21 new tests; end-to-end browser check of all three roles
- [ ] Email delivery (sign-up confirmation, password reset by email, status-change notifications); needs an SMTP provider
- [ ] Interview scheduling and messages between recruiter and candidate
- [ ] Per-company roles (owner vs member) and SSO for companies
- [ ] Playwright role checks in CI (they run locally today)

## Ongoing

- [ ] Keep `docs/` in sync: architecture diagram, model docs, eval results per phase
- [ ] Track LLM cost per CV and keep it under a budget
- [ ] Demo dataset + seed script for presentations
