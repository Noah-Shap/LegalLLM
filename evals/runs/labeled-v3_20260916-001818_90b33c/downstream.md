# Downstream: citation resolution and BM25 retrieval on each method's span

Spans from `evals/runs/labeled-v3_20260916-001818_90b33c` · 120 gold docs · resolver cache `data/processed/citation_cache.json` (15697 entries, **no network calls**) · BM25 fitted on the canonical build's train split minus the gold docs (550 of 587 rows; 37 gold docs excluded) · fixed targets = the gold span's resolved citations · 31 queries with ≥ 1 target.

Baseline reproduction on the build's own test split (rules spans, parquet text, BM25 on the full train split): Recall@10 **0.104**, MRR@10 0.217, n = 131.

## Citation resolution (cache lookups of case citations found in the span)

| metric | rules_v2 | llm-v1 | llm-v2 | llm-v3 | gold |
|---|---:|---:|---:|---:|---:|
| docs with a span | 100/120 | 82/120 | 79/120 | 87/120 | 87/120 |
| docs with ≥ 1 resolved citation (all gold docs) | 42.5% | 25.8% | 24.2% | 26.7% | 25.8% |
| docs with ≥ 1 resolved citation (docs that have a facts section) | 46.0% | 32.2% | 33.3% | 36.8% | 35.6% |
| unique case cites / resolved / cached-unresolved / uncached | 965 / 628 / 337 / 0 | 170 / 78 / 56 / 36 | 118 / 74 / 34 / 10 | 134 / 86 / 38 / 10 | 158 / 105 / 43 / 10 |
| resolved-target precision vs gold span | 15.1% | 88.5% | 95.9% | 96.5% | 100.0% |
| resolved-target recall vs gold span | 90.5% | 65.7% | 67.6% | 79.0% | 100.0% |
| spurious targets on no-facts docs (docs / targets) | 11/33 / 192 | 3/33 / 8 | 0/33 / 0 | 0/33 / 0 | 0/33 / 0 |

## BM25 retrieval (query = masked span text; targets fixed per doc)

| metric | rules_v2 | llm-v1 | llm-v2 | llm-v3 | gold |
|---|---:|---:|---:|---:|---:|
| Recall@10 (n = 31) | 0.126 | 0.145 | 0.120 | 0.145 | 0.143 |
| MRR@10 | 0.130 | 0.139 | 0.064 | 0.139 | 0.134 |
| Recall@10, queries where the method has a span | 0.135 (n=29) | 0.167 (n=27) | 0.133 (n=28) | 0.145 (n=31) | 0.143 (n=31) |
| Recall@10 with the build's own (rules-derived) targets (n = 49) | 0.149 | 0.115 | 0.108 | 0.118 | 0.117 |

Paired Recall@10 vs `rules_v2`: `llm-v1` wins 2 / ties 28 / losses 1 · `llm-v2` wins 1 / ties 26 / losses 4 · `llm-v3` wins 2 / ties 28 / losses 1 · `gold` wins 1 / ties 29 / losses 1

## How to read this

- *Resolved* means the normalized citation is in the resolver cache with a CourtListener cluster id; *uncached* citations were never submitted to the resolver (this run makes no network calls), so the resolution rates are lower bounds for every method alike.
- A rules span that spills into the Argument section resolves *more* citations, not fewer — the precision/recall rows against the gold span's targets, and the spurious-target row on documents with no facts section, show whether those extra targets are real facts-section citations.
- Recall@k asks whether the masked span text retrieves training briefs that cite the same cases. An empty span is an empty query (recall 0), so the all-queries row penalises has-facts mistakes and anchor failures; the span-found row isolates query quality.
