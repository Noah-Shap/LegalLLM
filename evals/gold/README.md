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
