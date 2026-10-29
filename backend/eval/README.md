# Evaluation harness

Offline evaluation of the AI components. It runs against the real LLM, so **each run costs API money**. At the default
settings (`claude-opus-5-5`, effort `medium`) a full run is 9 documents, usually one LLM call each, and costs
roughly a dollar. The exact cost is printed and saved with every run.

## Extraction (Phase 1)

```bash
cd backend
export ANTHROPIC_API_KEY=...            # or `ant auth login`
uv run python -m eval.run_extraction    # all cases
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
