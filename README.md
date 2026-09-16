# Legal Facts Extraction Service

[![CI](https://github.com/Noah-Shap/LegalLLM/actions/workflows/ci.yml/badge.svg)](https://github.com/Noah-Shap/LegalLLM/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Extracts the **Statement of Facts** from U.S. court briefs — the span plus parties, procedural posture, dated
events and citations as a validated JSON object — with an LLM extractor that replaced a rule-based heuristic, and
an evaluation loop that shows where it wins, where it doesn't, and what it costs.

This is an extraction pipeline with a disciplined eval loop, not a trained legal model. The repo was a data-curation
pipeline (CourtListener/RECAP → PDF → text/OCR → heading heuristics → citation resolution → retrieval baselines);
Phase 1 (Sep 2026) turned the extraction step into a deployed service and built the evals around it.

**Live demo:** _pending_ — the Hugging Face Space in [`deploy/`](deploy/README.md) needs an API key to serve the
LLM methods; the rules baseline runs without one.

## Results (120 gold documents, `evals/RESULTS.md`)

| | rules_v2 (baseline) | llm-v2 (Sonnet 5) | **llm-v3 (routed)** |
|---|---:|---:|---:|
| span IoU vs gold, mean | 0.572 | 0.912 | **0.975** |
| docs with IoU ≥ 0.9 | 46.7 % | 90.0 % | **95.8 %** |
| span IoU on the 35 human-labeled docs only | 0.647 | 0.869 | — |
| citation fidelity (emitted cites found verbatim in the source) | 1.000 | 0.962 | 0.964 |
| citation support (verbatim or page-number-supported) | 1.000 | 0.985 | 0.986 |
| structured fields (parties / posture / events per doc) | — | 99 % / 97 % / 7.1 | 99 % / 97 % / 7.2 |
| resolved-citation **precision** vs the gold facts section | 15.1 % | 95.9 % | **96.5 %** |
| resolved-citation recall vs the gold facts section | 90.5 % | 67.6 % | 79.0 % |
| cost / doc (API list price) | $0 | $0.274 | $0.331 |
| latency / doc | 0.01 s | 34 s | 37 s (≈ 99 s when escalated) |

Paired on the same documents, llm-v3 beats the rules baseline on 77, ties on 40, loses on 3.

**Headline finding.** The rule-based extractor looked good on the pipeline's old downstream metric — it resolved at
least one case citation on 42.5 % of documents versus 26.7 % for llm-v3 — but only **15 % of those citations
actually sit in the facts section**. The rest leak in from the table of contents and the Argument; the rules
emitted 192 citation targets on 11 documents that have *no* facts section at all. The LLM spans resolve fewer
citations because a correct Statement of Facts cites few cases. The old 58.5 % "resolution rate" was rewarding
the wrong thing.

**Where the LLM loses.** Retrieval. BM25 Recall@10 with the facts text as the query is flat across every span
source, including the human gold span (0.12–0.15 on the 31 gold docs with targets), so span quality is not the
bottleneck for that task — the retriever is. This matches the April 2026 result where dense, hybrid and reranker
baselines all lost to BM25 (Recall@10 0.104 on the canonical build's test split; the M4 milestone was not met),
and it is stated here rather than implied away.

**Failure analysis** (`evals/error_taxonomy.md`): the rules extractor's errors are systematic — spans that start on
the cover or table of contents (34), spill into the Argument (19), or are emitted on documents that are not
briefs (25 with no facts section at all); every `low`-confidence rules span was wrong (23/23). The LLM's residual
errors were 8 documents where Sonnet's quoted anchors could not be located in the PDF text (dropped hyphens,
merged headers); routing those 8 to Opus 5 recovered all of them, which is what llm-v3 is. Still open: citation
list/range expansion ("App. 1494, 1503" → "App. 1503"), handled by the *support* tier of the validator rather than
fixed in the prompt; and 10 citations the resolver cache has never seen.

**How the labels were made.** 120 documents: the pipeline's existing 100-doc audit set plus 20 documents where the
rules found nothing. An Opus 5 judge rated every candidate span with the labeling rubric and proposed corrected
boundaries; Noah reviewed the 35 hardest cases (every "partially correct" verdict, every unresolved doc, a sample
per accept policy). Judge↔human agreement on that overlap: rating κ **0.885**, has-facts κ **1.00**, span IoU
0.935 — so the judge's labels are used, tagged separately from the human ones, and every table can be re-run on
the human labels alone (`--labeler human`).

## Architecture

```
PDF / text ──► pypdf → PyMuPDF → (OCR) ──► normalize + preprocess (offset contract: doc_sha1 pins the text)
                                                       │
                          ┌────────────────────────────┼───────────────────────────────┐
                          ▼                                                            ▼
                 rules_v2 (frozen baseline)                              llm-v3  = Sonnet 5, prompt v2
                 heading map → merge → validate                          anchors → span located in text
                          │                                              ▼   anchor failure / validator flag / error
                          │                                          escalate → Opus 5, same prompt, effort high
                          ▼                                                            │
                   FactsExtraction (pydantic, schema 1.1, provenance) ◄────────────────┘
                          │
        deterministic validators: span bounds + text match · citation fidelity/support · dates · injection guard
                          │
       ┌──────────────────┼────────────────────┬──────────────────────┐
       ▼                  ▼                    ▼                      ▼
 POST /extract        Streamlit UI       eval harness            request log (JSONL, no text)
 (FastAPI)            rules vs LLM       vs 120-doc gold         → evals/dashboard.md
                                         judge (Opus 5, κ)
                                         downstream: resolver, BM25
                                         CI smoke gate (offline)
```

A **workflow**, deliberately not an agent: a fixed sequence with one routing decision and typed fallbacks. Design
notes and tradeoffs (anchors instead of offsets, whole-document instead of chunking, routing thresholds, judge
validation, prompt caching, cost projection) are in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Run it

```bash
git clone https://github.com/Noah-Shap/LegalLLM.git && cd LegalLLM
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

legallm-extract brief.pdf --method rules_v2 --json       # no model needed
export ANTHROPIC_API_KEY=sk-...                          # or, locally: --backend claude-cli (claude.ai login)
legallm-extract brief.pdf --method llm-v3 --json         # Sonnet 5, Opus 5 on failure

legallm-api --port 8000                                  # POST /extract, GET /health
curl -F file=@brief.pdf -F method=llm-v3 localhost:8000/extract
legallm-ui                                               # side-by-side UI (Streamlit)
```

Evals (offline where possible; LLM runs are cached by prompt sha × model × document sha):

```bash
legallm-gold stats                                       # gold set: ids + offsets + labels only
legallm-xeval --methods rules_v2 llm-v2 llm-v3 --subset labeled --offline   # metrics from cache
legallm-xeval --render evals/runs/<run_id>               # -> evals/RESULTS.md
legallm-downstream --run evals/runs/<run_id>             # resolver % + BM25 Recall@10 per span source
legallm-judge --run evals/runs/<run_id> --methods rules_v2 llm-v2   # Opus 5 judge (needs a backend)
legallm-gate                                             # CI regression gate on the smoke fixtures
legallm-dashboard                                        # evals/dashboard.md from the request log + runs
```

The CI gate replays frozen model responses for three synthetic briefs and fails the build if span IoU drops
more than 2 points, citation fidelity more than 1 point, or any extractor errors — see
[`evals/ci/`](evals/ci/) and the `gate` job in [`.github/workflows/ci.yml`](.github/workflows/ci.yml). A
deliberately regressed branch produces:

```
## Smoke regression gate: FAIL
| method | metric | baseline | current | Δ | max drop | status |
|---|---|---:|---:|---:|---:|---|
| llm-v2 | iou_mean | 0.955 | 0.867 | -0.088 | 0.02 | **FAIL** |
| llm-v3 | iou_mean | 0.955 | 0.867 | -0.088 | 0.02 | **FAIL** |
```

## Security and reliability

- API keys live in the environment only. Locally the extractors can run on a claude.ai subscription through the
  headless CLI (`--backend claude-cli`); that backend strips the API key from the child environment and is not
  deployable. Cost figures are the CLI's estimate at API list prices; those runs were subscription-billed.
- The document is untrusted input. The system prompt is fixed per version, the document appears only in the user
  turn, output is schema-constrained JSON, every span is re-located in the document text, and every emitted
  citation is checked against it. A guard flags instruction-like text in the document (`injection_suspected:*`)
  and fails validation if it reaches the model's output fields (`injection_in_output:*`); the service can refuse
  such documents (`LEGALLM_GUARD_MODE=block`).
- Retries with backoff on the model call; one retry on transient CLI failures; the strong tier is a fallback for the
  cheap tier's errors. Requests are rate-limited and size-capped; the request log records metadata, never text.
- Public court filings only; no PII beyond what the briefs already contain.

## Limitations

- **Retrieval did not improve** with better spans (above). The citation-prediction task needs a better retriever
  before extraction quality matters to it.
- **Gold labels are judge-assisted.** 35 of 120 are human; the rest are Opus 5 verdicts accepted under explicit
  policies after the κ check. Judge and extractor are both Claude models, so a same-family bias is possible; the
  human-only column is the control.
- **Deploy needs a funded API key.** The subscription backend cannot be hosted.
- **Deliberate gaps.** No agent harness or multi-agent orchestration (Phase 2); drift detection is nominal
  (a weekly scheduled run of the same smoke gate). U.S. briefs only. The rule-based extractor is frozen, not
  improved. No fine-tuning, no self-hosting.
- The canonical dataset build is `46864ffb7283` (1,599 spans); the April retrieval reports in `reports/m4_*`
  were computed on an earlier, overwritten build and are not directly comparable.

## Repository map

| path | what |
|---|---|
| `src/legallm/` | package: `schema.py`, `baseline_adapter.py`, `llm_extractor.py`, `prompts.py`, `routing.py`, `validators.py`, `guard.py`, `single_doc.py`, `api.py`, `ui_app.py`, `extraction_eval.py`, `judge.py`, `downstream_eval.py`, `ci_gate.py`, `observability.py`; the original pipeline (`pipeline.py`, `citation_*`, `baselines.py`, `eval_harness.py`) |
| `evals/` | `RESULTS.md`, `error_taxonomy.md`, `iterations.md`, `dashboard.md`, `gold/` (ids + offsets + labels, labeling guide), `runs/`, `judge/`, `ci/` |
| `docs/intent.md` | the target state, decisions log and definition of done for Phase 1 |
| `ARCHITECTURE.md` | tradeoffs and scaling notes |
| `deploy/`, `Dockerfile` | Hugging Face Space (UI) and API container |
| `STATE.md`, `GAP.md` | the measured inventory before Phase 1 and the component gap map |
| `tests/` | 470+ offline tests (`pytest tests/`), fixtures incl. frozen model responses for the CI gate |

The pipeline that builds the dataset (`legallm --query …`) hits the CourtListener API and needs `CL_TOKEN`; see
[`data/README.md`](data/README.md). It is not needed to run the service or the evals.

## License

[MIT](LICENSE)
