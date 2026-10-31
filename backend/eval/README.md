# Evaluation harness

Offline evaluation of the AI components, run against the configured LLM (`LLM_PROVIDER`). With the default local
model (Ollama, `mistral`) a run is free but slow, about 1–2 minutes per document on a 6 GB GPU. With
`LLM_PROVIDER=anthropic` (`claude-opus-5-5`, effort `medium`) a full extraction run costs roughly a dollar. The cost and
the model are saved with every run.

## Extraction (Phase 1)

```bash
cd backend
uv run python -m eval.run_extraction    # all cases, local model (ollama serve must be running)
uv run python -m eval.run_extraction --only en-03 --effort low
```

Each run writes `eval/results/extraction-<timestamp>.json`. That file holds the per-case scores, the false
positives and false negatives (for review) and the configuration (model, effort, prompt versions). Commit the
result files you want to compare.

### Data set: `eval/data/`

- `cvs/*.txt`: synthetic CVs (3 EN, 3 FR), rendered to PDF at run time so the real ingestion path is exercised.
  - `en-03-adversarial` contains hidden white text with a prompt injection and fake skills.
  - `en-02` and `fr-02` state a date of birth and marital status, which must *not* be extracted.
- `cvs/*.gold.json`: hand-written gold labels (skills, experiences, education, certifications, CEFR levels), plus
  `must_not_contain`, `hidden_text` and `expect_flags`.
- `jobs/*.txt` + `*.gold.json`: job descriptions with required and preferred skills, contract type, work mode,
  minimum years, languages and currency.

To add a case, drop a `name.txt` and a `name.gold.json` next to the existing ones.
`tests/test_eval_harness.py` checks that every case has a valid gold file.

### Metrics

| Metric | Meaning |
|---|---|
| `*_precision / *_recall / *_f1` | Set matching with normalization, an alias table and fuzzy matching. Skills use strict matching ("SQL" ≠ "SQL Server"); organisations and titles use lenient matching. |
| `unverified_rate` | Share of extracted items whose evidence quote was **not** found in the source text. This is the hallucination signal. |
| `sensitive_leaks` | Protected attributes (date of birth, marital status, ...) that appear in an extracted profile. Target: 0. |
| `missing_security_flags` | Expected document flags (hidden text, prompt injection) that were not raised. Target: 0. |
| `scalar_accuracy` | Name, email, job title, contract type, work mode, minimum years, currency. |
| `mean_latency_ms`, `total_cost_usd` | Per-run cost and speed. |

Gold skill lists include skills mentioned only in experience bullets. Precision is therefore a lower bound:
review `false_positives` before concluding that the model invents things. `unverified_rate` is the stricter
hallucination measure.

## Matching (Phase 2)

```bash
cd backend
uv run python -m eval.run_matching      # deterministic, free: no LLM call
```

- `data/matching/candidates/*.json`: candidate profiles as a correct extraction of each CV would produce them.
  This evaluates matching independently of extraction quality. `en-03` carries an unverified (hidden-text)
  Kubernetes claim, which must earn no credit.
- `data/matching/jobs/*.json`: the 3 jobs as validated requirement grids.
- `data/matching/relevance.json`: graded labels (0–3) for all 18 pairs. **They were written before the engine**, so
  they are not fitted to it.

The ranking matches what the recruiter sees: candidates passing knock-outs first, then knocked-out ones, each
group by score. Metrics: NDCG@3, NDCG@all, Spearman correlation between scores and labels, and top-1 accuracy.
`tests/test_matching_eval.py` fails CI if top-1 accuracy drops below 1, NDCG@3 below 0.9 or Spearman below 0.7.

| Engine | NDCG@3 | NDCG@all | Spearman | Top-1 |
|---|---:|---:|---:|---:|
| `match-v1` | 0.972 | 0.989 | 0.816 | 3/3 |

With 6 candidates and 3 jobs, these numbers detect regressions; they are not evidence of real-world accuracy.

## Retrieval (Phase 4)

```bash
cd backend
uv run python -m eval.run_retrieval     # needs Postgres; runs in a rolled-back transaction
```

The 6 labelled candidates are hidden among 300 deterministic synthetic distractors (nurses, accountants, PHP/MySQL
developers, QA testers, …; `eval/distractors.py`). For each job, we measure recall@K of the candidates labelled
relevant (≥ 1) in the shortlist that would be scored.

| Embedder | Hybrid R@10 | Vector-only R@10 | Full-text-only R@10 | Hybrid R@20 |
|---|---:|---:|---:|---:|
| `hashing-ngram-v1-384` | 1.000 | 0.889 | 1.000 | 1.000 |

The distractors are mostly far from the target roles, so this is an easy setting; it guards against regressions
and gives a baseline for comparing a neural embedding model.

## Agent (Phase 5)

```bash
cd backend
uv run python -m eval.run_agent                 # 30 cases
uv run python -m eval.run_agent --only fairness
```

Runs each request of `data/agent/cases.json` as a new conversation over the demo seed, inside a rolled-back
transaction. Proposed actions are never confirmed.

| Metric | Meaning |
|---|---|
| `completion_rate` | The conversation finished without an error. |
| `tool_selection_accuracy` | Every `must_call` tool was used (e.g. `explain_match` for "why does X score lower"). |
| `no_forbidden_tool_rate` | No `must_not_call` tool was used (e.g. no stage change when only asked for an opinion). |
| `confirmation_gating_accuracy` | The proposed actions are exactly `expect_pending`: actions when asked, none otherwise. |
| `mean_model_calls`, `mean_latency_ms`, `total_cost_usd` | Efficiency. |

Cases marked `manual_review` (fairness refusals, emails, privacy, invented scores) are listed in the summary; read
their `reply` in the results file. A refusal cannot be graded reliably by keyword matching.

## Results so far

| Run | Model | Highlights |
|---|---|---|
| `extraction-20261031-132655` | mistral 7B (Ollama, GPU) | skills F1 0.917 · required skills 1.0 · languages 0.978 · unverified 4.0% · sensitive leaks 0 · 69 s/doc · $0 |
| `agent-20261031-131613` | mistral 7B, structured tools | 12/30 · completion 1.0 · tool selection 0.47 · forbidden tools 0 · gating 0.83 · fairness 4/4 · 21 s/request |
| `agent-20261030-050725` | mistral 7B, native tools | 6/30 · tool selection 0.30 (no tool ever called; replies described the tools or invented data) |
