# Critical Evaluation: v0.2 Spec Package & Roadmap

## Overall Assessment

Both documents are well-structured and substantially more mature than a typical v0.2 planning artifact. The spec package demonstrates genuine domain awareness (legal citation semantics, PACER/RECAP licensing nuances, OCR routing), and the roadmap ties milestones to concrete Definition-of-Done gates rather than vague timelines. That said, several gaps, inconsistencies, and risks deserve attention before locking scope for Sprint 1.

---

## 1. Spec Package (`approved_spec_package_v0_2.md`)

### Strengths

- **Dataset Inclusion Policy is the standout section.** Deterministic, rule-based doc-type validation with explicit exclusion codes is exactly what's needed to prevent garbage-in problems. The sealed/restricted marker detection is a good defensive measure.
- **Label semantics are well-scoped.** The decision to exclude short-form cites (`Id.`, `supra`) from Phase-1 labels with an auditable `excluded_reason` avoids a class of noisy-label problems that would be painful to debug later.
- **Data contracts are precise.** Six schema tables with required/optional markings and join keys give downstream consumers (ML Eng, eval harness) a concrete interface to code against.
- **Failure taxonomy is comprehensive.** Covering the full pipeline from FETCH through RESOLVE with reproducible repro pointers (`pdf_sha256`, `build_id`, `git_commit`) is strong engineering practice.

### Weaknesses & Gaps

#### 1.1 Facts Span Extraction is Underspecified

The spec devotes significant rigor to doc-type validation and citation resolution but is surprisingly thin on the *core* task: extracting the facts section.

- **No fallback strategy.** What happens when a brief uses a non-standard heading (e.g., "Nature of the Case", "Factual Background", "Preliminary Statement")? The structure indicators in the doc-type validation gate list only four patterns. The actual facts extractor presumably needs a broader vocabulary, but this isn't specified.
- **No max-length guardrail definition.** The spec mentions `facts_len` should be "within expected bounds (configurable)" but never defines defaults. A facts span that captures 90% of a 60-page brief is structurally valid but semantically wrong. This needs a concrete ceiling (e.g., facts_len < 40% of full_text_len or < 15,000 chars).
- **No handling of briefs with multiple fact-like sections.** Some briefs have both "Statement of Facts" and "Procedural History" as distinct sections. The spec doesn't say whether to merge them, pick the first, or pick the longest.

#### 1.2 Citation Masking Strategy is Incomplete

- The spec says to mask citations with `[CITATION]` but doesn't define the masking scope. Does this mask only the formal citation string (e.g., `Smith v. Jones, 500 U.S. 1 (1990)`) or also parenthetical descriptions and subsequent references to "the Smith court" or "in Smith"? If the latter aren't masked, the leakage controls are weaker than they appear.
- No specification of which masking regex or tool is used, or whether masking is validated against the `targets_all` list (it should be — otherwise you could mask some citations while missing others that happen to be in the label set).

#### 1.3 Resolver Confidence Policy Has an Untested Assumption

- The 0.90 confidence threshold is stated as a default but there's no empirical basis cited. If the resolver (presumably CourtListener's API) returns confidence scores at all, it's not clear that 0.90 is a meaningful cutoff vs. 0.80 or 0.95. This should be explicitly flagged as "to be calibrated during M2" rather than presented as a spec'd default.

#### 1.4 Gold Audit Set Design Has Sampling Bias Risk

- Stratifying by `needs_ocr`, `source_system`, and page-length bins is sensible, but 50–200 briefs (default 100) may be too small to detect rare but systematic failure modes. With 10 strata (2 OCR × 1 source × 5 length bins) you get ~10 briefs per stratum — barely enough for statistical confidence on the 80% facts-correctness threshold.
- The audit rubric (`correct` / `partially_correct` / `incorrect`) is defined for facts spans but no inter-rater reliability protocol is mentioned. If only one person audits, the "≥ 80% correct" threshold is subjective.

#### 1.5 Schema Gaps

- `modeling_row` has no `needs_ocr` field. This means stratified eval reporting (which requires `needs_ocr`) must join back to `extraction_artifact`. This is workable but adds friction. Consider denormalizing.
- `modeling_row` has no `document_type` field, same issue for stratified reporting by document type.
- `citation_targets_artifact` records `cache_hit_rate` as a float, but this is a per-build aggregate, not per-row. Its placement at the row level is misleading — it should be in `build_manifest.json` instead.
- No schema is defined for `build_manifest.json` itself, despite it being referenced as a required output in multiple places.

#### 1.6 Operational Envelope is Optimistic

- **1,000 briefs for MVP** is reasonable, but the 10,000 stretch target combined with a 25,000-lookups/day resolver budget and $100/week OCR ceiling creates tension. A brief with 30 unique citations × 10,000 briefs = 300,000 resolver lookups. At 25,000/day, that's 12 days just for resolution (assuming zero cache hits on a first build). This should be explicitly modeled.

---

## 2. Roadmap (`roadmap_risk_register_stakeholder_schedule_v0_2.md`)

### Strengths

- **Milestones have real DoD gates**, not just "feature complete." M1 requires reproducible rebuild + exclusion-rate reporting; M3 requires leakage tests to pass. This is good discipline.
- **Risk register is specific and actionable.** Each risk has a named owner and concrete mitigations rather than generic "monitor and escalate" language.
- **Licensing decision tree is governance-ready.** The distinction between internal-only (brief text) and publishable (identifiers/hashes/labels) with 180-day retention defaults is practical and defensible.

### Weaknesses & Gaps

#### 2.1 Sprint Plan is Unrealistic for Sprint 1

Sprint 1 packs four substantial work items:
1. Dataset Inclusion Policy gates + doc-type validation
2. Standardize `needs_ocr` decision module
3. Build manifest + deterministic `build_id`
4. Failure taxonomy end-to-end coverage

Each of these involves new schema definitions, new validation code, new logging infrastructure, and integration testing. For a 2-week sprint this is aggressive even with a dedicated Data Engineering team. The risk is that all four ship at 80% and none are truly "done" by DoD standards.

**Recommendation:** Prioritize items 1 and 4 (inclusion policy + failure taxonomy) as Sprint 1, defer manifest/build_id to Sprint 2. The `needs_ocr` module already exists per CLAUDE.md (`ocr_decision.py`), so "standardize" may mean "test and document" rather than "rewrite" — but this should be explicit.

#### 2.2 No Dependency Graph Between Sprints

The sprint plan reads as a flat list but has implicit dependencies:
- Sprint 3 (resolver + splits) depends on Sprint 2 (citation extraction + normalization) being complete.
- Sprint 4 (baselines + eval harness) depends on Sprint 3 (splits with dedupe controls) being complete.
- Gold Audit Set (Sprint 2) depends on Sprint 1 (failure taxonomy + inclusion policy) to be meaningful.

These dependencies aren't called out, which means a slip in Sprint 2 silently delays everything downstream. A simple dependency diagram or critical-path annotation would help.

#### 2.3 Risk Register Omits Key Risks

Missing risks:
- **CourtListener API changes or deprecation.** The entire resolver and data acquisition layer depends on a third-party API. No mitigation is listed for API versioning, endpoint changes, or service discontinuation.
- **Facts extraction accuracy plateau.** The risk that heuristic-based facts extraction can't reach 85% success on diverse briefs is not listed. This is arguably the highest-impact technical risk for the project.
- **Team availability / bus factor.** The RACI-lite map assumes four distinct roles but doesn't address what happens if, say, the sole ML Engineer is unavailable during Sprint 4.
- **Data drift over time.** Court filing practices and brief formatting evolve. Rules tuned on 2020-era briefs may not generalize to 2025 filings.

#### 2.4 Licensing Section Has a Gap on Fair Use

The decision tree handles source-level licensing well but doesn't address the fair use analysis for extracted facts spans. Facts spans are *selections from copyrighted briefs* — even if the selection is a factual recitation. The spec assumes "internal-only" is sufficient protection, but if the project ever moves toward publication (the stretch goal), a fair use analysis should be on the governance reviewer's checklist. This is currently missing from "Required governance outputs per release."

#### 2.5 Stakeholder Review Cadence May Be Too Heavy

Weekly pipeline health dashboards, biweekly sprint reviews with Gold Audit readouts, and monthly governance reviews create a significant reporting overhead. For a small team running 2-week sprints, this means nearly continuous preparation of review artifacts. Consider whether the weekly dashboard can be automated (it should be a CI artifact, not a manually prepared report) and whether monthly governance can be async until a publication decision is imminent.

---

## 3. Cross-Document Inconsistencies

| Issue | Spec says | Roadmap says |
|---|---|---|
| OCR budget enforcement | `excluded_reason=ocr_budget_exceeded` (marks rows) | "defer new OCR jobs and log deferrals" (operational) |
| Who owns citation ambiguity | Label semantics are under ML Eng purview | Risk register assigns "ML Eng/Data Eng" jointly |
| Gold Audit Set timing | Required per `build_id` | First appears in Sprint 2, but M1 (Sprint 1–2) DoD doesn't mention it |
| Cache hit-rate reporting | Per-row field in `citation_targets_artifact` | "cache hit-rate tracked and reported" (build-level metric) |

These aren't fatal but signal that the two documents evolved somewhat independently and would benefit from a reconciliation pass.

---

## 4. Summary of Recommendations

1. **Specify the facts extractor in detail** — heading vocabulary, fallback logic, max-length guardrails, multi-section handling.
2. **Define citation masking scope precisely** — formal cites only vs. case-name references. Validate masking against the label set.
3. **Flag the resolver confidence threshold (0.90) as provisional** and plan calibration during M2.
4. **Increase Gold Audit Set minimum to 200** if stratifying across 10+ strata, or reduce strata count.
5. **Descope Sprint 1** to inclusion policy + failure taxonomy + `needs_ocr` validation (it already exists). Push manifest/build_id to Sprint 2.
6. **Add a sprint dependency graph** or critical-path annotations.
7. **Add missing risks:** CourtListener API stability, facts extraction accuracy plateau, fair use for publishable artifacts.
8. **Denormalize `needs_ocr` and `document_type` into `modeling_row`** to avoid join overhead for stratified eval.
9. **Move `cache_hit_rate` to `build_manifest.json`** and define the manifest schema.
10. **Automate the weekly dashboard** as a CI artifact to reduce reporting overhead.
11. **Reconcile the two documents** on OCR budget handling, Gold Audit timing relative to milestones, and cache hit-rate granularity.
