# Architecture and tradeoffs

The service turns one document into one `FactsExtraction` object. Everything else — the baseline, the evals, the
judge, the routing — exists to know whether that object is right and what it costs. This page records the choices
and why; the results they produced are in `evals/RESULTS.md`, the decision history in `docs/intent.md` §11.

## 1. Workflow, not agent

The path is fixed: text → extractor → validators → (routing) → output. There is exactly one decision point (escalate
or not) and it is made by deterministic checks, not by a model. Reasons: the task has a stable shape, every step is
individually testable, the cost of a request is bounded (at most two model calls), and failures are typed. An agent
harness would buy flexibility the task does not need and would make the eval loop harder to reason about. This is
a stated non-goal for Phase 1, not an omission.

## 2. Anchors instead of offsets

The model never emits character positions. It returns the first and last few words of the facts section verbatim;
the code locates those anchors in the document text (whitespace/quote-tolerant, then an 8/6/4-word relaxation) and
derives the span. Offsets from a model are wrong in ways that are hard to detect; anchors are either found or not,
and "not found" is an explicit, routable failure (`anchor_not_found`) rather than a silently misplaced span. The
price is the 8/120 documents where Sonnet quoted text the PDF layer rendered differently (dropped hyphens, merged
headers) — the class that routing exists for.

All offsets refer to one canonical text: `preprocess_text(normalize_text(raw))`, computed to a fixed point, with
`doc_sha1` pinning it. Gold labels, cached extractions, and API responses share that contract, so a span is
meaningful across runs.

## 3. Whole document, not chunks

Briefs are long (median ≈ 91k characters on the gold set) but almost all fit in a 400k-character head window, and
the facts section is located by structure that a chunk boundary can cut through (a heading on one side, the
Argument on the other). Chunking would add a merge step and a second failure class. Documents beyond the window
are truncated to the head with a `doc_truncated_to_window` note; 6 of the 120 gold documents were (the longest is
977k characters), and all six kept IoU 1.0 because a Statement of Facts sits near the front of a brief.

## 4. Two tiers and one routing rule

`llm-v3` runs Sonnet 5 (prompt v2, effort medium) and escalates to Opus 5 (same prompt, effort high) only when the
cheap pass fails a deterministic check: anchors not located although the model said a facts section exists, a span
validator flag, or a transport/schema error. A "no facts section" verdict never escalates: the judge found all 33
of those correct, so escalation there would spend money confirming the cheap tier. Unsupported-citation flags are
not a trigger either — they fire on a fifth of documents through list/range expansion, the judge rated those spans
correct, and Opus shares the habit.

Effect on the gold set: 8 escalations (6.7 % of documents), 8 recovered spans, IoU 0.912 → 0.975, cost $0.274 →
$0.331 per document. Escalated documents take ≈ 99 s end to end (both passes). Both passes are kept in provenance
so the log can show which tier answered and why.

Prompt v1 and v2 are frozen and content-hashed; the hash is part of every cache key, run manifest and log line. A
prompt change is a new version with a before/after row in `evals/iterations.md`.

## 5. Validators are the product boundary

The model's output is accepted only after deterministic checks against the source text: span within bounds and
byte-identical to the text; every emitted citation found verbatim (whitespace/hyphen/dash/quote-insensitive) or,
failing that, supported by its page numbers near the same prefix — a two-tier check that separates "the model
invented a cite" (fails) from "the model expanded a printed list" (flagged, counted, allowed); dates parseable;
non-empty facts when the document is a merits brief; and the injection guard (§7). The rules baseline passes these
by construction, which is why its "validator pass" column is not a quality signal on its own.

## 6. Evals: deterministic first, judge second, humans as ground truth

- **Deterministic**: span IoU vs gold, an IoU-derived 3-class rating calibrated against human ratings (92 %
  agreement on the rules spans), citation fidelity/support, recovered-span rate on documents where the rules found
  nothing, field coverage, cost and latency — all from cached extractions so a re-score is free.
- **Judge**: Opus 5 reads the document with both candidate spans marked inline, rates each with the labeling rubric,
  codes the issue, and proposes corrected anchors. Its verdicts became labels only after a human overlap of 35
  documents gave κ 0.885 on the rating and 1.00 on has-facts; they stay tagged `judge:…` and every table can be
  re-run on human labels only. Caveat kept visible: judge and extractor are the same model family.
- **Downstream**: the pipeline's own citation resolver (cache only, no network) and BM25 retrieval re-run on each
  method's span with fixed per-document targets, so the comparison isolates the span. This is what exposed the
  rules extractor's resolution rate as leakage.
- **Gate**: three synthetic briefs whose raw model responses were recorded once and are replayed through the real
  extractor in CI (anchor location, parsing, validators, routing all execute); IoU −2 pts or fidelity −1 pt fails
  the build. The first version replayed finished extractions and let a deliberate regression through — a useful
  reminder that a gate has to be shown failing before it is trusted. The same job runs weekly as the drift check.

## 7. Security model

The document is untrusted. Structural isolation: fixed system prompt, document only in the user turn, JSON schema
on the output, anchors and citations re-verified against the text. Detection on top: instruction-like passages and
zero-width/bidi runs in the document raise `injection_suspected:*` (extraction proceeds; the API can block); the
same patterns in the model's free-text fields fail validation (`injection_in_output:*`), because that is the model
following the document. Keys live in the environment; the headless-CLI backend used for local runs strips the API
key from the child process and runs in an empty directory so no repository instructions reach the prompt. The
request log stores metadata and a document hash, never text.

## 8. Cost, latency, scaling

Per document at API list prices (Sonnet 5 $2/$10 per Mtok, Opus 5 $5/$25): llm-v2 ≈ $0.27, llm-v3 ≈ $0.33, i.e.
**≈ $330 per 1,000 documents** with routing, ≈ $270 without, versus $0 for the rules baseline. Latency is
model-bound (34–37 s per document sequentially); throughput scales with concurrency, not per-request work, so a
batch of 1,000 documents at 8 concurrent requests is roughly 1.5 hours. Levers, in order: prompt caching of the
fixed system prompt (already in place through the API's cache fields; the document itself is not cacheable across
requests), lower effort on the cheap tier for short briefs, and a batch endpoint for offline builds. The resolver's
budget tracker and the cost report from the original pipeline are the same pattern applied to the new calls.

Local development runs on a claude.ai subscription through the headless CLI, which reports the same cost estimate
but bills nothing per token; that backend cannot be deployed.

## 9. What would change next

- A retriever that uses the structured fields (parties, posture, events) rather than the masked span text — the
  downstream eval showed span quality is no longer the bottleneck.
- A prompt v3 that fixes citation list expansion at the source, measured against the support metric.
- A second annotator on the 35-doc overlap to turn κ into inter-annotator agreement rather than judge-vs-one-human.
- Phase 2: an agentic layer only if a task appears that a fixed workflow cannot express.
