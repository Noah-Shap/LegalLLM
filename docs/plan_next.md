# Plan — next work after Phase 1

Two items, each with phases that stop at a measurable checkpoint. Estimates are working time for Claude Code plus
wall time for model runs on the subscription backend (`claude-cli`); no API credits are needed unless stated.
Rules R1–R7 in `CLAUDE.md` apply throughout; R5 (no live CourtListener calls) is the one this plan may ask to lift.

Baselines these plans must beat (from `evals/RESULTS.md` and `evals/runs/labeled-v3_20260916-001818_90b33c/downstream.md`):

| metric | value | where |
|---|---|---|
| BM25 Recall@10, canonical build test split, rules spans | 0.104 (n = 131) | downstream baseline |
| BM25 Recall@10, gold docs with targets, any span source | 0.12–0.15 (n = 31) | downstream table |
| citation fidelity (strict verbatim), llm-v3 | 0.964 | headline table |
| citation support (verbatim + components), llm-v3 | 0.986 | headline table |
| non-verbatim (expanded) citations, llm-v3 | 150 across 86 docs with cites | headline table |
| span IoU, llm-v3 | 0.975 | must not drop |

---

## Item 1 — a retriever that uses the structured fields

**Question.** Does retrieval improve when the query is built from what the LLM extracted (posture, events, parties)
instead of the masked facts narrative? Phase 1 showed the narrative query is flat across span sources, including
gold, so the query representation is the suspect, not the span.

### Phase 1A — asymmetric field-weighted query (≈ 3 h, no model calls)

The 120 gold documents already have structured fields (cached llm-v3 extractions). The BM25 index stays what it
is: training briefs' masked narratives. Only the query changes.

1. `downstream_eval.py`: add a *query builder* abstraction — today the builder is `mask_citations(span_text)`;
   register named builders: `narrative` (current), `fields` (posture + event texts + parties, each repeated by a
   weight), `fields+narrative` (fields prepended to the narrative), `events_only`.
2. Run all builders on the 31 gold queries with the existing train-minus-gold index; report Recall@10 / MRR@10 and
   the paired wins/ties/losses vs `narrative`, per builder.
3. Sweep the field weights (1, 3, 5 repeats) on the same queries; note this is tuning on the eval set and treat any
   gain as a hypothesis for 1B, not a result.

*Checkpoint.* A builder that beats `narrative` on the paired comparison (wins − losses ≥ 8 of 31) earns Phase 1B.
If nothing does, the conclusion is recorded in `evals/iterations.md` and Phase 1B is skipped.

### Phase 1B — symmetric field index (≈ 4 h work + ≈ 5.5 h model time)

The asymmetric query in 1A matches fields against narratives. A fair test indexes fields on both sides.

1. Run llm-v3 over the canonical build's training rows that are not gold documents (550 rows). The existing
   harness caches by prompt sha × model × document sha, so this is a one-time cost (≈ 34 s/doc → ≈ 5.5 h on the
   subscription, ≈ $150 at API list prices if ever re-run on a key). Add `legallm-xeval --gold <manifest of train
   rows>` support or a small `legallm-fields` runner that writes a parquet of fields keyed by `search_result_id`.
2. Build BM25 indexes over (a) training narratives, (b) training posture+events, (c) both concatenated. Evaluate
   the 31 gold queries and, once the 131 test rows also have fields (another ≈ 1.2 h of model time), the full
   test split — the number that is comparable to the 0.104 baseline.
3. Add the best configuration as a `baselines.py` class (`FieldsBM25Baseline`) so `legallm-eval` can run it beside
   the April baselines, and record the result in `reports/`.

*Checkpoint.* Recall@10 on the 131-query test split > 0.104 with a paired-comparison margin (wins − losses > 0 and
bootstrap 95 % interval of the mean delta above 0). Anything else is a negative result worth one paragraph.

### Phase 1C — index the cited cases themselves (decision needed)

The pipeline resolves citations to CourtListener cluster ids but never fetches case text. Retrieving cases directly
(facts → case) instead of via other briefs (facts → similar brief → its citations) is the obvious next target, but
it needs case text for the ~2,000 distinct target ids: a live CourtListener fetch, which R5 forbids today.

*Decision for Noah:* lift R5 for a bounded, cached fetch (opinion text for the target cluster ids only, ≈ 2k calls,
within the existing budget tracker)? If yes: ≈ 6 h work — fetcher with cache, case index (BM25 over opinion
syllabus/head), facts-to-case Recall@10 on the same test split. If no: Phase 1 stops at 1B.

### Risks

- 31 gold queries detect large effects only; every 1A gain must be confirmed on the 131-row test split in 1B.
- Fields from the LLM for training rows are extracted from *rules* spans' documents but the LLM reads the whole
  document, so this is not contaminated by the rules span — but the targets still are (they came from rules spans;
  §G of the taxonomy showed 85 % of them are Argument leakage). A cleaner label set would re-resolve targets from
  llm-v3 spans; that changes the task definition and is a Phase-2 decision, not a side effect of this plan.

---

## Item 2 — prompt v3: citation list expansion fixed at the source

**Problem.** The model expands printed citation lists/ranges ("2-ER-104, 106" → "2-ER-106") into strings that do
not appear in the document. Prompt v2's instruction did not stop it (152 expansions). Phase 1 papered over it with
the validator's *support* tier. The fix should make the failure impossible rather than tolerated.

### Phase 2A — structured record citations (≈ 4 h work + ≈ 70 min model time)

1. `schema.py`: `LlmFactsOutput.record_citations` becomes `list[RecordCite]` with `RecordCite(prefix: str,
   pages: list[str], as_printed: str)`; `FactsExtraction.record_citations` keeps the flat string form for
   downstream compatibility, rendered from `as_printed`. Case citations stay strings (expansion there was rare).
2. `prompts.py`: `FACTS_SYSTEM_V3 / USER_V3` = v2 text plus the schema description: copy `as_printed` exactly as it
   appears, put the page list in `pages`. New frozen sha; `PROMPT_VERSIONS += ("v3",)`; `llm-v3` today is the
   *routed* method — name collision. Resolution: prompt versions and method names are decoupled: the routed method
   becomes configurable (`RouteConfig(cheap_version="v3")`) and is registered as `llm-v4`; `llm-v3` stays as-is for
   reproducibility.
3. `validators.py`: fidelity checks `as_printed` verbatim (strict), and separately checks that every page in
   `pages` appears within the component window (this replaces the heuristic support tier with a check the schema
   makes explicit).
4. Run `legallm-xeval --methods llm-v3 llm-v4 --subset labeled --backend claude-cli` (120 docs, ≈ 70 min, cached
   thereafter); `legallm-judge` is *not* needed — IoU vs gold is direct.
5. Re-record the gate fixtures (`legallm-gate --record`) and `--update-baseline`; add an `llm-v4` row to
   `evals/iterations.md` and close taxonomy class L3 in `evals/error_taxonomy.md`.

*Checkpoint.* Strict citation fidelity ≥ 0.98 (from 0.964) **and** span IoU within 0.01 of llm-v3 **and** record
cites per document within 10 % of today's 31. A fidelity gain bought with dropped citations fails the checkpoint.

### Phase 2B — fallback if the schema change hurts recall (≈ 2 h)

Keep v2's free-string output and add a deterministic post-processor: for each emitted record citation not found
verbatim, search the component window for a printed list containing the same prefix and page and replace the
emitted string with the printed form. Measured with the same three criteria; this is a code-only change, so the
gate fixtures do not need re-recording.

### Risks

- Sonnet 5 rejects `temperature`; effort stays `medium`. Drift on v3 was 30/30 pairs at IoU ≥ 0.999 for v2 — re-run
  the 10-doc × 3 drift check for the new prompt before trusting single runs.
- The routed method's cheap tier changes model output distribution; the 8 anchor-failure documents may shift. The
  escalation count is a reported number, not a target.

---

## Order and effort

| step | work | model time | needs Noah |
|---|---|---|---|
| 2A prompt v3 + structured cites | 4 h | 70 min | — |
| 1A field-weighted query | 3 h | — | — |
| 1B symmetric field index | 4 h | ≈ 6.7 h (background) | — |
| 2B fallback (only if 2A fails) | 2 h | — | — |
| 1C case index | 6 h | ≈ 2k CourtListener calls | **R5 decision** |

Do 2A first: it is self-contained, closes the last open validator class, and its 70-minute run can overlap with
1A's code work. Then 1A → 1B. 1C only after an explicit R5 decision. Every step ends with a row in
`evals/iterations.md` and, if a number in `README.md` changes, a re-render of `evals/RESULTS.md`.
