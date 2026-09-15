# evals/gold — human-labeled gold set (C5)

| File | Tracked | Contents |
|---|---|---|
| `gold_v1.jsonl` | yes | one `GoldRecord` per line: ids, strata, rules_v2 span, human label (rating, gold span offsets, notes) |
| `gold_v1.meta.json` | yes | build parameters (seed, counts, offset contract) |
| `LABELING_GUIDE.md` | yes | rubric, boundary rules, ambiguity rules |
| brief text | **no** | regenerated from `data/raw/pdfs/<id>.pdf` (gitignored); `doc_sha1` pins it |

Composition (D6): the 100-document audit set sampled 2026-04-06 (seed 42, stratified by rules confidence ×
length bin) plus 20 `no_facts_span` failures from the 2k build, sampled with seed 42 from the 370 failures whose
PDF is local.

Offsets are into `preprocess_text(normalize_text(raw))` — the same text `legallm-extract` and every extractor
use — so gold spans, rules spans, and LLM spans are directly comparable (span IoU, C6).

Rebuild from scratch (destroys labels): `legallm-gold init --force`.

## Labeling provenance (2026-09-15)

Labels were produced judge-assisted: an Opus 5 judge (`evals/judge/`) rated every candidate span and its verdicts
were attached as suggestions; 85 records were bulk-accepted under explicit policies (`labeler = "judge:claude-opus-5"`),
and Noah reviewed 35 (`review_set_v1.txt`: the 2 unresolved, the 19 partially-correct verdicts, 3 per policy),
recording human labels (`labeler = "noah"`). Judge↔human κ: 0.885 (rating), 1.00 (has_facts); span IoU 0.935.
`legallm-xeval --labeler human` restricts gold to the human labels.
