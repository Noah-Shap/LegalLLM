# Downstream: citation resolution and BM25 retrieval on each method's span

Spans from `evals/runs/labeled-v5_20260916-132745_3eac2d` · 120 gold docs · resolver cache `data/processed/citation_cache.json` (15697 entries, **no network calls**) · BM25 fitted on the canonical build's train split minus the gold docs (550 of 587 rows; 37 gold docs excluded) · fixed targets = the gold span's resolved citations · 31 queries with ≥ 1 target.

Baseline reproduction on the build's own test split (rules spans, parquet text, BM25 on the full train split): Recall@10 **0.104**, MRR@10 0.217, n = 131.

## Citation resolution (cache lookups of case citations found in the span)

| metric | rules_v2 | llm-v2 | llm-v3 | llm-v4 | llm-v5 | gold |
|---|---:|---:|---:|---:|---:|---:|
| docs with a span | 100/120 | 79/120 | 87/120 | 84/120 | 87/120 | 87/120 |
| docs with ≥ 1 resolved citation (all gold docs) | 42.5% | 24.2% | 26.7% | 25.0% | 26.7% | 25.8% |
| docs with ≥ 1 resolved citation (docs that have a facts section) | 46.0% | 33.3% | 36.8% | 34.5% | 36.8% | 35.6% |
| unique case cites / resolved / cached-unresolved / uncached | 965 / 628 / 337 / 0 | 118 / 74 / 34 / 10 | 134 / 86 / 38 / 10 | 130 / 84 / 36 / 10 | 134 / 86 / 38 / 10 | 158 / 105 / 43 / 10 |
| resolved-target precision vs gold span | 15.1% | 95.9% | 96.5% | 96.4% | 96.5% | 100.0% |
| resolved-target recall vs gold span | 90.5% | 67.6% | 79.0% | 77.1% | 79.0% | 100.0% |
| spurious targets on no-facts docs (docs / targets) | 11/33 / 192 | 0/33 / 0 | 0/33 / 0 | 0/33 / 0 | 0/33 / 0 | 0/33 / 0 |

## BM25 retrieval (query = masked span text; targets fixed per doc)

| metric | rules_v2 | llm-v2 | llm-v3 | llm-v4 | llm-v5 | gold |
|---|---:|---:|---:|---:|---:|---:|
| Recall@10 (n = 31) | 0.126 | 0.120 | 0.145 | 0.145 | 0.145 | 0.143 |
| MRR@10 | 0.130 | 0.064 | 0.139 | 0.139 | 0.139 | 0.134 |
| Recall@10, queries where the method has a span | 0.135 (n=29) | 0.133 (n=28) | 0.145 (n=31) | 0.155 (n=29) | 0.145 (n=31) | 0.143 (n=31) |
| Recall@10 with the build's own (rules-derived) targets (n = 49) | 0.149 | 0.108 | 0.118 | 0.118 | 0.118 | 0.117 |

## Query builders (plan 1A): same index and targets, different query text (Recall@10 / MRR@10)

| method | narrative | fields | fields3 | fields5 | fields+narrative | fields3+narrative | events |
|---|---:|---:|---:|---:|---:|---:|---:|
| llm-v2 | 0.120 / 0.064 | 0.165 / 0.131 (5/25/1) | 0.164 / 0.141 (5/25/1) | 0.164 / 0.141 (5/25/1) | 0.146 / 0.121 (3/28/0) | 0.153 / 0.128 (4/27/0) | 0.165 / 0.133 (5/25/1) |
| llm-v3 | 0.145 / 0.139 | 0.163 / 0.150 (2/27/2) | 0.163 / 0.152 (2/27/2) | 0.163 / 0.152 (2/27/2) | 0.144 / 0.143 (0/30/1) | 0.152 / 0.144 (1/29/1) | 0.164 / 0.152 (2/28/1) |
| llm-v4 | 0.145 / 0.139 | 0.165 / 0.161 (3/27/1) | 0.165 / 0.158 (3/27/1) | 0.165 / 0.158 (3/27/1) | 0.153 / 0.145 (1/30/0) | 0.169 / 0.145 (2/29/0) | 0.164 / 0.158 (2/28/1) |
| llm-v5 | 0.145 / 0.139 | 0.165 / 0.161 (3/27/1) | 0.165 / 0.158 (3/27/1) | 0.165 / 0.158 (3/27/1) | 0.153 / 0.145 (1/30/0) | 0.169 / 0.145 (2/29/0) | 0.164 / 0.158 (2/28/1) |

Cells: Recall / MRR, then paired wins/ties/losses against that method's own `narrative` query. Fields = procedural posture + key-event texts + parties from the method's extraction; a number after `fields` is how many times the fields text is repeated (a crude term weight). The checkpoint in `docs/plan_next.md` §1A is wins − losses ≥ 8 of 31 for some builder.

Paired Recall@10 vs `rules_v2`: `llm-v2` wins 1 / ties 26 / losses 4 · `llm-v3` wins 2 / ties 28 / losses 1 · `llm-v4` wins 2 / ties 28 / losses 1 · `llm-v5` wins 2 / ties 28 / losses 1 · `gold` wins 1 / ties 29 / losses 1

## How to read this

- *Resolved* means the normalized citation is in the resolver cache with a CourtListener cluster id; *uncached* citations were never submitted to the resolver (this run makes no network calls), so the resolution rates are lower bounds for every method alike.
- A rules span that spills into the Argument section resolves *more* citations, not fewer — the precision/recall rows against the gold span's targets, and the spurious-target row on documents with no facts section, show whether those extra targets are real facts-section citations.
- Recall@k asks whether the masked span text retrieves training briefs that cite the same cases. An empty span is an empty query (recall 0), so the all-queries row penalises has-facts mistakes and anchor failures; the span-found row isolates query quality.
