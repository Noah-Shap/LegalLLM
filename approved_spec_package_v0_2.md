# Problem + Scope Spec (v0.2)

## Problem statement
Legal researchers often start with a **fact pattern** (what happened, procedural posture) and need to identify **likely controlling / persuasive precedents**. This project builds an end-to-end pipeline that ingests **merits briefs (PDFs)**, extracts a **facts span**, and learns a model that predicts **citation targets** (cases/opinions) that the brief ultimately cites.

The pipeline is explicitly designed as a **retrieval-style prediction task**: *given facts text*, predict *which cases are cited* (and later, which cases should be retrieved).

---

## Inputs / outputs

### Primary input (raw)
- **Merits brief PDF** (typically party-filed; includes facts + argument + citations).
- Provenance fields (minimum):
  - `source_system` (e.g., CourtListener/RECAP)
  - `source_id` (stable upstream identifier)
  - `pdf_url`
  - `document_type` (brief/motion/etc.)
  - `download_timestamp`
  - `sha256_pdf`

---

## Dataset Inclusion Policy (v0.2)

This policy defines which documents are eligible to become dataset rows and converts downstream ambiguity into an upstream, deterministic contract. Documents that fail eligibility MUST be logged as `DOC_TYPE_MISMATCH` with a specific `validation_reason`.

### Eligibility: what counts as a “merits brief”
A document is eligible **only if** it is a party-filed merits-stage brief (or equivalent) intended to argue the merits of the case, such as:
- opening/appellant/petitioner brief
- response/appellee/respondent brief
- reply brief (optional; include if present and labeled as merits-stage)
- supplemental merits briefs explicitly designated by the court (optional)

### Explicit inclusions
- Party merits briefs that contain (or are expected to contain) a narrative section such as **Statement of Facts**, **Statement of the Case**, or **Background**.
- Briefs where the “facts” section is combined with “case” (e.g., “Statement of the Case and Facts”).

### Explicit exclusions (not eligible for this dataset build)
- **Amicus briefs** (default: exclude)
- **Appendices / addenda / record excerpts**
- **Tables of Authorities**, **Tables of Contents**, **Certificates of Compliance/Service**
- Motions, letters, orders, opinions, transcripts, exhibits
- Sealed/restricted documents or documents with restricted markers (see below)

If excluded, record:
- `excluded_by_policy=True`
- `excluded_policy_rule=<RULE_ID>`
- `validation_reason=<human-readable short reason>`

### Sealed / restricted markers
Exclude documents if any of the following are true:
- Upstream metadata indicates sealed/restricted/non-public
- The PDF is encrypted/password-protected
- First-page text contains strong sealed markers (e.g., “SEALED”, “FILED UNDER SEAL”, “CONFIDENTIAL”)

### Deterministic doc-type validation (aligned to `DOC_TYPE_MISMATCH`)
Validation MUST be deterministic and based on a **ruleset** (no LLM required).

1) **Metadata gate (hard rules)**
- Require `document_type` in allowlist (configurable).
- Exclude if title/short description contains exclusion keywords (e.g., “appendix”, “table of authorities”, “certificate”).

2) **First-pages text gate (soft rules with thresholds)**
Extract text from the first N pages (default N=2–3) and apply:
- Require at least one *brief indicator*: `BRIEF`, `OPENING BRIEF`, `REPLY BRIEF`, `APPELLANT`, `APPELLEE`, `PETITIONER`, `RESPONDENT`
- Require at least one *structure indicator*: `STATEMENT OF FACTS`, `STATEMENT OF THE CASE`, `BACKGROUND`, `PROCEDURAL HISTORY`
- Exclude if dominated by TOA/TOC patterns (dense dotted leaders, high ratio of page references)

3) **Decision + logging**
- Emit `doc_type_validated=True/False`
- If False: `failure_code=DOC_TYPE_MISMATCH` and `validation_reason` capturing which gates failed.

### Required fields (new)
- `doc_type_validated` (bool)
- `validation_reason` (string; short)
- `excluded_by_policy` (bool)
- `excluded_policy_rule` (string; e.g., `EXC_AMICUS`, `EXC_APPENDIX`, `EXC_SEALED`, `EXC_TOO_LONG`)

---

## Intermediate artifacts

### 1) Extracted full text
- `full_text`
- `text_extractor` (e.g., pymupdf_text, pdfminer, etc.)
- `needs_ocr` (boolean; computed by standardized heuristic)
- `ocr_engine` + version + settings (if used)

### 2) Facts span
- `facts_start`, `facts_end` (character offsets into `full_text`)
- `facts_text`
- `facts_len`
- `facts_extractor_method` + `facts_extractor_notes`

### 3) Citation targets
- `raw_citations` (strings as found)
- `normalized_citations` (canonicalized)
- `resolved_targets` (preferred): canonical IDs (e.g., CourtListener opinion/cluster IDs)
- `resolution_method`: API verification/mapping (preferred) with fallback local resolver

#### Label semantics (tightened)
**Definition of a “citation target” (Phase-1):**
- Targets are **judicial opinions/cases** only, represented as canonical IDs.
- Non-case references (statutes, regulations, secondary sources, court rules) are **not** targets in Phase-1.

**Handling rules**
- **Parallel citations:** multiple strings referring to the same case MUST collapse to a single canonical target ID. Preserve all observed strings in an audit trail.
- **Short-form cites (“Id.” / “Ibid.” / “supra” / “infra”):** treat as `target_type=unknown` unless resolvable deterministically from nearby full citations. Default Phase-1 behavior: **exclude from labels** with `excluded_reason=context_dependent_short_form`.
- **String cites / pincites:** include only if the string contains enough information to resolve to the case; otherwise exclude with `excluded_reason=insufficient_case_identifier`.
- **Non-case references:** extract for auditing but exclude from Phase-1 labels.

**New fields (required)**
Represent extracted references as objects so filtering is auditable:
- `target_type` ∈ `{case, statute, regulation, secondary, rule, unknown}`
- `excluded_reason` (string; required when not included as a Phase-1 label)
- `resolution_status` ∈ `{resolved, unresolved, excluded}`
- `resolved_id` (string; present when resolved)
- `resolved_source` (e.g., `courtlistener_api`, `local_resolver`)

**Recommended representation**
- `targets_all`: list[object] (all extracted references, including excluded)
- `targets_case_ids`: list[string] (the Phase-1 label set used for modeling)

---

## Resolver architecture + constraints (v0.2)

### Preferred flow (privacy- and reliability-preserving)
1) **Local extraction** from `full_text` → candidate citation strings  
2) **Normalization** (reporter, volume, page, court/year where available)  
3) **Verification/mapping** via resolver API **with normalized citation strings only**  
   - Do **not** transmit full briefs or large spans of brief text.

### Chunking and request-size constraints
- Batch normalized citations into chunks (default: 25–100 cites per request, configurable).
- Enforce a per-build and per-hour request budget:
  - `api_budget_per_build_id`
  - `api_budget_per_hour`
- If budget exceeded: stop resolution, mark remaining as unresolved with `excluded_reason=api_budget_exceeded`.

### Caching policy
- Cache by `normalized_citation` → `(resolved_id, resolution_status, confidence, timestamp, resolver_version)`
- Cache MUST persist across runs for cost control and reproducibility.
- Cache invalidation occurs only when resolver logic/version changes (recorded in `build_manifest.json`).

### Retry / backoff
- Exponential backoff with jitter on transient failures (HTTP 429/5xx/timeouts).
- Hard stop after `max_retries` (default 5). Log resolver-specific failures.

### Confidence policy (in-spec)
Resolution is accepted as `resolved` only if:
- Resolver returns a single unambiguous match AND key fields match exactly; OR
- Top candidate has an exact match on normalized fields and confidence ≥ `min_confidence` (default 0.90)

Otherwise:
- Mark `resolution_status=unresolved`
- Do not include as Phase-1 label; set `excluded_reason=low_confidence_or_ambiguous`.

---

## Modeling dataset row (training/eval)
- **Model input:** `facts_text_masked` (facts text with citations masked; raw facts retained for auditing)
- **Model output/labels (Phase-1):** `targets_case_ids` (multi-label set) and/or ranked list ground truth

---

## Explicit non-goals (for this phase)
- Full brief segmentation into all rhetorical roles (facts/argument/standard-of-review/relief requested).
- Modeling that generates “novel” citations not present in a known corpus.
- End-user product UI, drafting assistance, or legal advice.
- HITL labeling at scale (spot checks only; bounded audit set allowed).
- Cross-jurisdiction deep normalization beyond resolver capability (e.g., complex parallel/short-form linking), until baseline resolver is stable.

---

## Success metrics + acceptance thresholds

### A) Dataset build (pipeline health)
**Definition:** % of input PDFs that successfully produce a modeling row with non-empty `facts_text` and ≥1 resolved Phase-1 case target.

**Acceptance thresholds (MVP)**
- **PDF acquisition success:** ≥ 98% of reachable URLs downloaded with checksum recorded.
- **Text extraction success:** ≥ 92% produce `full_text` above a minimum size threshold (configurable by doc type).
- **OCR routing correctness (spot-checked):** ≥ 95% of image-only / near-image-only PDFs are flagged `needs_ocr=True`.
- **Doc-type validation:** ≥ 95% precision on the gold audit set (see E) for “eligible merits brief” vs excluded.
- **Facts span success:** ≥ 85% of eligible briefs produce a facts span with:
  - `facts_len` within expected bounds (configurable; guardrails to avoid grabbing entire brief)
  - `facts_start < facts_end`
- **Citation target success:** ≥ 90% of successful facts spans yield ≥ 1 **resolved** Phase-1 case target.

### B) Failure taxonomy (required)
Every failure must emit **one** primary failure code + optional secondary detail to a structured log (e.g., `facts_failures.jsonl`), including:
- `FETCH_FAIL` (HTTP/timeout)
- `PDF_CORRUPT_OR_ENCRYPTED`
- `TEXT_EXTRACT_EMPTY`
- `NEEDS_OCR_FALSE_NEGATIVE`
- `OCR_FAIL`
- `DOC_TYPE_MISMATCH`
- `FACTS_SECTION_NOT_FOUND`
- `FACTS_SPAN_OUT_OF_BOUNDS`
- `CITE_PARSE_FAIL`
- `CITE_RESOLUTION_LOW_CONFIDENCE`

**Acceptance:** 100% of failures have a taxonomy code + reproducible repro pointer (`pdf_sha256`, step name, exception hash).

### C) Reproducibility requirements
- End-to-end dataset build is reproducible from:
  - pinned dependencies + `git_commit`
  - immutable input manifest (list of source IDs/URLs + checksums)
- Every dataset artifact includes a `build_manifest.json` capturing versions + parameters.
- Determinism:
  - Non-LLM steps must be deterministic.
  - OCR must record engine + language pack + config; tolerate minor OCR nondeterminism but require stable pass/fail behavior.

### D) Initial modeling metric targets (intentionally modest)
**Evaluation metrics**
- Retrieval-style: `Recall@K`, `MRR@K`, `nDCG@K` on ranked case lists.
- Label-style (optional): micro-F1 on top-N predictions.

**Targets (Phase-1)**
- Baseline 0 (popularity): establish floor.
- Baseline 1 (lexical retrieval): **Recall@10 ≥ 0.10**, **MRR@10 ≥ 0.05**
- Baseline 2 (dense retrieval): beat Baseline 1 on Recall@10 by **+10% relative**.

#### Stratified reporting (required)
Report `Recall@K`, `MRR@K`, `nDCG@K` stratified by:
- **Label-cardinality bins** (targets per brief): 1, 2–3, 4–7, 8+
- `source_system`
- `needs_ocr` (True/False)
- `document_type` (if multiple types are permitted by policy)

#### Popularity / leakage checks (required)
- Report popularity-only baseline vs learned models.
- Compute overlap with global most-cited list; flag dominance by frequency.
- Enforce citation-masking checks in the eval harness; fail the run if unmasked citations leak into model input.

### E) Gold Audit Set (bounded HITL; required)
This is a small manual audit to prevent optimizing structurally-valid but semantically-wrong artifacts while remaining consistent with “spot checks only.”

**Sampling**
- Per `build_id`, sample **50–200 briefs** (default 100) stratified by:
  - `needs_ocr` (True/False)
  - `source_system`
  - brief length bins (e.g., <20 pages, 20–60, >60)

**Audit dimensions**
1) **Facts span correctness**
- Pass if `facts_text` substantially captures narrative facts/background and is not dominated by argument, TOA/TOC, or boilerplate.
- Rubric: `correct` / `partially_correct` / `incorrect`.

2) **Resolution correctness**
- For each audited brief, sample up to K resolved case targets (default K=10) and verify the resolved ID matches the cited case.

**Acceptance thresholds (per build_id)**
- Facts span: ≥ 80% `correct` (count `partially_correct` as fail for MVP unless relaxed)
- Resolution: ≥ 95% correct among audited resolved targets
- Output: `audit_readout_<build_id>.md` including top failure patterns + fixes.

---

## Leakage controls (must-have)
- If facts text contains citations, mask them (`[CITATION]`) for modeling runs (keep raw for auditing).
- Split strategy prevents near-duplicates across train/test (by docket/brief ID + fuzzy hash of extracted text).
- Do not use citation-graph edges that directly encode the label when building features.
- Eval harness enforces “no unmasked citations in input.”

---

## Definition of Done (DoD)

### DoD: Approved spec
- Inputs/outputs + schemas defined and versioned.
- Dataset Inclusion Policy finalized (eligibility/exclusions + deterministic validation).
- Label semantics for targets are explicit and auditable (`target_type`, `excluded_reason`).
- Resolver confidence policy + API/caching constraints are in-spec.
- Success metrics + acceptance thresholds agreed, including Gold Audit Set.
- Risks + mitigations reviewed with stakeholders.
- Licensing/usage posture documented (internal vs publishable artifacts).

### DoD: Dataset builder v1
- Produces:
  - versioned dataset artifact(s) (e.g., `facts_dataset.parquet`)
  - `build_manifest.json` (versions, params, commit, timestamps)
  - `facts_failures.jsonl` (failure taxonomy)
  - exclusion-rate report (`excluded_by_policy` grouped by rule)
- Meets MVP thresholds for acquisition/extraction/facts/targets.
- Re-runnable reproducibly from manifest inputs.
- CI checks for:
  - schema validity
  - failure taxonomy completeness
  - regression set of “hard PDFs” (OCR routing + extraction + doc-type validation)

### DoD: Baseline modeling + eval harness
- Baselines implemented: popularity, BM25/lexical, dense retrieval (or hybrid).
- Leakage checks enforced:
  - masked-citation input for training/eval
  - split-level duplicate detection
- Stratified metric reporting (label-cardinality bins, `source_system`, `needs_ocr`, `document_type`).
- Popularity-dominance checks and leakage test gate (fail run on unmasked citations).

---

## Data contract (schemas)

### 1) `pdf_manifest` (input index)
| Field | Type | Required | Notes |
|---|---|---:|---|
| `source_system` | string | ✅ | e.g., courtlistener_recap |
| `source_id` | string | ✅ | stable upstream ID |
| `pdf_url` | string | ✅ | retrieval location |
| `document_type` | string | ✅ | brief/motion/etc. |
| `download_timestamp` | datetime | ✅ | UTC |
| `sha256_pdf` | string | ✅ | checksum |
| `local_path` | string | ✅ | path in storage |

### 2) `inclusion_validation_artifact` (new)
| Field | Type | Required | Notes |
|---|---|---:|---|
| `sha256_pdf` | string | ✅ | join key |
| `doc_type_validated` | bool | ✅ | eligible merits brief? |
| `validation_reason` | string | ✅ | short reason |
| `excluded_by_policy` | bool | ✅ | exclusion applied? |
| `excluded_policy_rule` | string | ⛔/✅ | required if excluded |

### 3) `extraction_artifact`
| Field | Type | Required | Notes |
|---|---|---:|---|
| `sha256_pdf` | string | ✅ | join key |
| `text_extractor` | string | ✅ | extractor name |
| `extractor_version` | string | ✅ | pinned |
| `needs_ocr` | bool | ✅ | standardized heuristic |
| `ocr_engine` | string | ⛔/✅ | required if `needs_ocr=True` |
| `ocr_version` | string | ⛔/✅ | required if `needs_ocr=True` |
| `full_text` | string | ✅ | extracted text |
| `full_text_len` | int | ✅ | chars |

### 4) `facts_span_artifact`
| Field | Type | Required | Notes |
|---|---|---:|---|
| `sha256_pdf` | string | ✅ | join key |
| `facts_start` | int | ✅ | char offset in `full_text` |
| `facts_end` | int | ✅ | char offset in `full_text` |
| `facts_text` | string | ✅ | substring |
| `facts_len` | int | ✅ | chars |
| `facts_extractor_method` | string | ✅ | heuristic/LLM/etc. |
| `facts_extractor_notes` | string | ⛔ | diagnostics |

### 5) `citation_targets_artifact` (updated)
| Field | Type | Required | Notes |
|---|---|---:|---|
| `sha256_pdf` | string | ✅ | join key |
| `targets_all` | list[object] | ✅ | includes excluded |
| `targets_case_ids` | list[string] | ✅ | Phase-1 labels |
| `resolution_method` | string | ✅ | API/regex/etc. |
| `resolver_version` | string | ✅ | pinned |
| `api_budget_per_build_id` | int | ⛔ | recorded |
| `cache_hit_rate` | float | ⛔ | recorded |

**`targets_all` object schema**
- `original_text` (string)
- `normalized` (string)
- `target_type` (enum)
- `resolution_status` (enum)
- `resolved_id` (string | null)
- `excluded_reason` (string | null)
- `resolved_source` (string | null)
- `confidence` (float | null)

### 6) `modeling_row` (final dataset)
| Field | Type | Required | Notes |
|---|---|---:|---|
| `row_id` | string | ✅ | stable |
| `sha256_pdf` | string | ✅ | provenance |
| `facts_text` | string | ✅ | raw facts |
| `facts_text_masked` | string | ✅ | model input |
| `targets` | list[string] | ✅ | case IDs |
| `split` | string | ✅ | train/val/test |
| `build_id` | string | ✅ | links to manifest |

---

## Failure taxonomy (enumeration)
Each failure record MUST include:
- `timestamp`
- `step` (FETCH / VALIDATE / EXTRACT / OCR / FACTS / CITES / RESOLVE)
- `failure_code`
- `exception_type`
- `exception_message_hash`
- `pdf_url`
- `sha256_pdf` (if available)
- `repro` (local path + build_id + git_commit)

Codes:
- `FETCH_FAIL`
- `PDF_CORRUPT_OR_ENCRYPTED`
- `TEXT_EXTRACT_EMPTY`
- `NEEDS_OCR_FALSE_NEGATIVE`
- `OCR_FAIL`
- `DOC_TYPE_MISMATCH`
- `FACTS_SECTION_NOT_FOUND`
- `FACTS_SPAN_OUT_OF_BOUNDS`
- `CITE_PARSE_FAIL`
- `CITE_RESOLUTION_LOW_CONFIDENCE`

---

## Appendix: Operational envelope (v0.2)

These are planning constraints that make throughput/cost assumptions explicit. Values are defaults and should be tuned as empirical telemetry accumulates.

### Expected corpus size
- Initial (MVP): **1,000** eligible merits briefs
- Stretch: **10,000** eligible merits briefs

### PDF size assumptions
- Typical brief length: 20–80 pages
- Hard cap for processing: 300 pages (configurable)
- If cap exceeded: exclude by policy (`EXC_TOO_LONG`) unless explicitly overridden.

### OCR expectations
- Expected OCR rate: 10–30% of eligible PDFs (source-dependent)
- OCR only when `needs_ocr=True` under standardized routing.

### Budget ceilings and enforcement
- OCR ceiling: **$100/week** (planning default)
  - If exceeded: pause new OCR jobs; continue non-OCR processing; mark deferrals with `excluded_reason=ocr_budget_exceeded`.
- Resolver/API ceiling: **25,000 normalized-citation lookups/day** (planning default)
  - If exceeded: stop further resolution for the build and mark remaining as unresolved (budget-exceeded), preserving extracted citations for later reprocessing.

### Run-level guardrails
Every run must output:
- total PDFs ingested
- % excluded by inclusion rules (by rule)
- OCR rate and OCR pages processed
- resolver calls made vs budget + cache hit rate
- final dataset yield (rows) and failure taxonomy distribution
