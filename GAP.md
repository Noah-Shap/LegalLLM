# GAP — target components vs. current repo

Snapshot 2026-09-14, commit 25554b4. Columns: **Target component** (from `intent.md` §5) ·
**Exists?** (Y / partial / N, citing `STATE.md` §) · **Notes** (left for chat-side Claude).

> **PROVISIONAL.** `intent.md` was 0 bytes at snapshot time, so §5 could not be read. The rows
> below are the components the session primer names (deployed LLM extraction app + disciplined
> eval loop). Replace the "Target component" column with the actual §5 list once `intent.md` is
> populated; the Exists? assessments for the underlying capabilities stay valid.

| Target component | Exists? | Notes |
|---|---|---|
| Document sourcing (CourtListener/RECAP search + PDF acquisition) | Y — STATE §3 stages 1–4; 7,502 PDFs local (§5) | |
| Text extraction with OCR routing (pypdf → PyMuPDF → Tesseract) | Y — STATE §3 stages 5–6, §2 `ocr_decision.py`/`ocr_backend.py` | |
| Rule-based facts-span extractor (baseline to compare LLM against) | Y — STATE §3 stage 8 (`rules_v2`), §6 quality signals | |
| Single-document end-to-end run path (one PDF/text in → facts out) | partial — STATE §4: only via `--max_docs 1` or Python calls; no CLI/function for a local file | |
| LLM extraction module (Claude API call, prompt, structured output) | N — STATE §10: no LLM code anywhere | |
| Structured output schema / validation for extraction results | N — STATE §10: no pydantic/instructor; parquet schema only (§5) | |
| Prompt versioning + build/prompt manifest | partial — STATE §2 `build_manifest.py` records params/git/deps; no prompt field | |
| Gold / labeled facts spans for eval | partial — STATE §5: 100-doc audit set sampled, 0/100 rated; no span-level labels | |
| Extraction eval harness (LLM vs rules vs gold; span overlap / correctness metrics) | N — STATE §2 `eval_harness.py` evaluates citation retrieval (Recall/MRR/nDCG), not span extraction | |
| Regression / eval dataset with fixed splits | partial — STATE §2 `dataset.py` dedup + split exists for retrieval rows; `tests/fixtures/` empty (§1) | |
| Cost, latency, token tracking for LLM calls | N — STATE §2 `generate_cost_report` covers resolver API calls only | |
| Deployed app / API surface (e.g., FastAPI endpoint) | N — STATE §4: CLI entry points only | |
| Citation extraction + resolution (downstream labels) | Y — STATE §3 stages 10–11; 58.5 % rows with ≥1 resolved target (§5) | |
| Retrieval baselines + eval (popularity/BM25/dense/hybrid/reranker) | Y — STATE §2 `baselines.py`, §7 reports (BM25 best, Recall@10 0.126) | |
| Tests passing offline | Y — STATE §8: 235 passed, ruff clean; mypy 3 errors | |
| CI running on push | partial — STATE §8: workflow exists but targets `main`; branch is `master`; 0 runs | |
| Failure taxonomy per spec v0.2 | partial — STATE §3 stage 12: 6 ad-hoc codes vs spec's 10 | |
| Provenance (sha256, needs_ocr, text_extractor in modeling row) | N — STATE §3 stage 13, §13 | |
| Public repo readable by chat-side Claude | N — STATE §11: private; zip archive produced instead (see session report) | |
| Secrets hygiene (.env ignored, no tokens in history) | Y — STATE §12 | |
| Data hygiene (data/, parquet, jsonl, pdf ignored) | Y — after `chore(repo): hygiene` (6d01dab) | |
