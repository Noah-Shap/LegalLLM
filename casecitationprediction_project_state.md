# CaseCitationPrediction Project State (as of 2026-02-21)

## 1) Project summary

This project is building a **benchmark-grade dataset** of **“facts” sections** extracted from U.S. court filings (primarily merits briefs) sourced via the **Free Law Project / CourtListener** ecosystem. The dataset is intended to support **legal citation prediction** experiments—i.e., modeling which authorities/case citations are likely to be relevant given a statement of facts (and related features/metadata).

Concretely, the pipeline:
- Searches CourtListener for RECAP documents matching a query.
- Downloads the corresponding PDFs.
- Extracts text via native PDF text extraction, and **falls back to OCR when necessary**.
- Uses rule-based heading detection to slice out the **Facts / Background** span.
- Writes a structured dataset (`facts_dataset.parquet`) and a detailed failure log (`facts_failures.jsonl`) for reproducibility and iterative improvement.

Key artifacts implied by current scripts and recent work:
- `data/raw/pdfs/<search_result_id>.pdf` — downloaded source documents
- `data/processed/facts_dataset.parquet` — extracted facts spans + quality flags
- `data/processed/facts_failures.jsonl` — per-document failure reasons + diagnostics
- `data/processed/pdf_parse_warnings.log` — pypdf/fitz parsing warnings


## 2) Current goals

### Primary goal
Produce a **high-quality, reproducible corpus** of facts-only text suitable for downstream modeling and evaluation of **case-citation behavior**, while minimizing bias toward text-native PDFs.

### Supporting goals
1. **Standardize OCR decision-making** across modules so the pipeline and OCR backend do not drift.
2. Reduce false failures by:
   - filtering out-of-scope filings (orders, transcripts, appendices, etc.) rather than labeling them “extraction failures”.
   - improving PDF URL resolution and download robustness.
3. Provide **diagnostic visibility** (reasons/metrics) into extraction quality and OCR decisions, enabling systematic tuning.


## 3) Implementation overview

### 3.1 Pipeline: search → download → extract → facts-span → dataset

The pipeline script (`run_pipeline_v3_abc_v3_updated_with_ocr.py`) implements:

**A. Search**
- Uses CourtListener REST v4 `BASE = "https://www.courtlistener.com/api/rest/v4"` and hits `GET /search/` with:
  - `type=rd` (“flat PACER documents” mode)
  - `available_only=on`
  - `order_by=score desc`
  - Optional `fields=...` to request helpful keys (when supported)

**B. PDF URL derivation**
- Prefers `filepath_local` in the search result (best signal; mapped to `https://storage.courtlistener.com/<filepath_local>`).
- Otherwise falls back to various PDF-ish fields (`download_url`, `file_url`, `pdf_url`, etc.).
- As a last resort, fetches a public CourtListener page and regex-extracts a `.pdf` href.

**C. Download robustness**
- Tries both `www.courtlistener.com/recap/...` and `storage.courtlistener.com/recap/...` URL variants.
- Detects “pending” non-PDF responses (notably HTTP 202 or non-%PDF payload) and retries with exponential backoff.

**D. Scope filtering (dataset definition)**
- `in_scope_brief(...)` aggressively selects “merits-ish” briefs and excludes:
  - non-brief filings (orders, mandates, transcripts, etc.)
  - motion/memo filings masquerading as briefs
  - amicus/reply briefs
  - claim construction briefs (by default)
- This is an explicit **coverage choice** to keep the dataset benchmark-focused and reduce noise.

**E. Text extraction (best-effort)**
- Primary extraction: `pypdf` (`page.extract_text()`).
- Fallback extraction: `PyMuPDF` (`fitz`) if:
  - no text is returned, or
  - the extracted text is likely unusable / OCR-needed.
- A standardized OCR decision (below) influences whether to attempt alternate extraction before OCR.

**F. OCR integration (optional)**
- If `--enable_ocr` is set and dependencies are available, OCR is performed via the PyMuPDF/Tesseract backend.
- OCR is selective at the page level (only “bad” pages are OCR’d) unless forced.

**G. Normalization + facts span extraction**
- `normalize_text` removes hyphen line breaks, collapses repeated whitespace/newlines, and strips trailing spaces.
- `extract_facts_span` tries (in order):
  1) exact heading match for facts starts/stops (STATEMENT OF FACTS, BACKGROUND, etc.)
  2) “soft” heading detection (any heading-like line with FACT/BACKGROUND/STATEMENT signals)
  3) fallback slice: beginning → ARGUMENT heading (when facts precede argument without a clear facts header)
- Skips TOC entries by detecting TOC markers + dot leaders/page numbers.

**H. Output + diagnostics**
- Writes `facts_dataset.parquet` with:
  - `facts_text`, `facts_start`, `facts_end`
  - metadata like `pdf_url`, `pdf_url_strategy`, `short_description`, `document_type`
  - quality flags: naive `cite_hits` and `arg_marker_hits` per 10k chars
- Writes `facts_failures.jsonl` with structured reasons:
  - `no_pdf_url`, `out_of_scope`, `pdf_pending`, `pdf_download_failed`
  - `needs_ocr` (with OCR reasons/metrics, snippets, and OCR backend metadata)
  - `no_facts_span` (with heading candidates and notes)


### 3.2 Standardized OCR decision module

`ocr_decision.py` centralizes OCR heuristics, providing:
- `should_ocr_document(doc_text, page_count=..., cfg=...)`
- `should_ocr_page(page_text, cfg=...)`

The logic is intentionally conservative and targets common court-filing extraction failure modes:
- **stamp-only / header-only**: PACER/ECF overlays extract but body is image-only
- **garbage extraction**: PDF internals (e.g., `/i255`) or extremely low alphabetic ratio
- **low density**: too little text overall, or too little text per page when page count is known

All decisions return `(bool, details)` where `details` includes:
- `reasons: list[str]`
- `metrics: dict`
- `cfg: dict` (for logging and threshold tuning)


### 3.3 OCR backend: PyMuPDF + Tesseract selective OCR

`pymupdf_ocr_backend_updated.py` implements:
- dependency/health checks (`check_ocr_ready`) for:
  - PyMuPDF OCR support (`Page.get_textpage_ocr`)
  - `tesseract` on PATH
  - `tessdata` and language traineddata availability
- selective OCR extraction:
  - native: `page.get_text("text")`
  - OCR: `page.get_textpage_ocr(...)` then `page.get_text("text", textpage=tp)`
  - page-level decision uses `ocr_decision.should_ocr_page(...)`
- CLI + an optional `--save-txt` to persist the extracted text alongside the PDF

The pipeline passes the shared `OcrDecisionConfig` into the backend (`decision_cfg=...`) so page-level and doc-level criteria remain aligned.


## 4) What changed recently (from chats + current files)

### OCR decision standardization
You requested a single standardized “needs OCR?” determination shared across the pipeline and OCR backend. That is now implemented via `ocr_decision.py`, and imported in both:
- pipeline: wrapper `doc_needs_ocr(...)` delegates to `should_ocr_document(...)`
- backend: `should_ocr_page(...)` drives selective page OCR

### Optional OCR output persistence
You asked for an option to save OCR output as `.txt`. The backend supports `save_txt`, and the pipeline exposes `--ocr_save_txt` to enable saving extracted output next to each PDF during OCR fallback.


## 5) Current status signals and likely next steps

### Status signals
- The pipeline is now structured to:
  - avoid obvious non-brief filings (scope filtering)
  - attempt multiple extraction strategies before declaring “needs_ocr”
  - attempt OCR only when enabled and only when indicated by standardized heuristics
- “needs_ocr” failures may still occur for at least three reasons:
  1) OCR not enabled or not available (dependencies missing)
  2) OCR attempted but produced empty/low-density text (`ocr_attempt_failed_or_empty`)
  3) OCR produced text but it still fails the `should_ocr_document` thresholds (`still_needs_ocr_after_ocr`)

### Practical next steps (engineering)
1. **Inspect `facts_failures.jsonl` distribution**
   - quantify top failure reasons and identify whether failures are mostly:
     - “out_of_scope” (expected, dataset definition)
     - “no_facts_span” (heading logic gaps)
     - “needs_ocr” (OCR readiness/quality issues)

2. **Tune OCR thresholds / decisions**
   - if OCR outputs still fail document-level thresholds, consider:
     - lowering `doc_min_total_chars` for certain document types
     - adjusting stamp-only thresholds (`*_min_body_chars`)
     - incorporating page-level OCR success signals into the doc-level pass/fail

3. **Improve facts-span extraction coverage**
   - add/adjust headings (court-specific variations)
   - incorporate a light-weight “section classifier” fallback for unusual formatting
   - store more structured heading diagnostics in failures for rapid iteration

4. **Add caching for OCR outputs**
   - backend includes SHA1-based caching helpers; integrating caching into the pipeline could reduce repeated OCR cost during iteration.


## 6) Source files reviewed

- `run_pipeline_v3_abc_v3_updated_with_ocr.py`
- `ocr_decision.py`
- `pymupdf_ocr_backend_updated.py`
