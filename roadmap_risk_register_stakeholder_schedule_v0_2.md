# Roadmap + Risk Register + Stakeholder Review Schedule (v0.2)

## Sprint cadence
- **2-week sprints**
- Weekly: 30m execution sync (pipeline health + blockers)
- End of sprint: demo + metrics readout + risk review
- Monthly: stakeholder checkpoint (data sources, API governance, licensing posture)

---

## Assumptions & limits (v0.2)

These assumptions constrain scope and convert “risks” into managed operating limits.

### Team coverage assumptions
- Data Engineering: owns ingestion, extraction, OCR routing, failure taxonomy, and exclusion-rate reporting.
- ML Engineering: owns evaluation harness, leakage controls, baselines, and audit readout integration.
- Infra/DevOps: owns job orchestration, caching/storage, CI, and budget enforcement.
- Governance reviewer: signs off on licensing/retention/publishing posture.

### OCR envelope
- Expected OCR rate: 10–30% of eligible PDFs.
- OCR cost ceiling: **$100/week** (planning default). If exceeded: defer new OCR jobs and log deferrals.

### Resolver/API usage envelope
- Local extraction first; transmit **normalized citation strings only**.
- Persisted cache required (cache hit-rate tracked and reported).
- Daily request budget (planning default): **25,000** normalized-citation lookups/day.
- Per-build request budget enforced via `api_budget_per_build_id`.

---

## Ownership map (RACI-lite)
- **PM/RM:** scope, acceptance criteria, stakeholder reviews, roadmap governance
- **Data Engineering:** ingestion, OCR routing, extraction pipeline, inclusion policy enforcement, logging/taxonomy
- **ML Engineering:** baselines, eval harness, leakage controls, model iteration, Gold Audit readouts
- **Infra/DevOps:** storage, caching, CI, reproducible builds, job orchestration, budget enforcement
- **Legal / Data Governance reviewer:** licensing/redistribution posture, retention rules, compliance review

---

## Milestones (deliverables + DoD gates)

### M0 — Approved spec
**Deliverables**
- Spec + DoD + data contracts + failure taxonomy
- Dataset Inclusion Policy finalized (eligibility, exclusions, deterministic validation rules)
- Label semantics for targets (target_type + excluded_reason) and resolver confidence policy

**DoD gate**
- Sign-off from PM/RM + Eng leads + Governance reviewer

### M1 — Deterministic dataset builder v1
**Deliverables**
- Versioned dataset artifact(s) + manifests
- Failure taxonomy fully populated in `facts_failures.jsonl`
- Exclusion-rate reporting (% excluded by policy rule)

**DoD gate**
- Meets MVP thresholds for acquisition/extraction/facts/targets
- Reproducible rebuild from manifest
- Inclusion/exclusion validation checks implemented; report `% excluded` by policy rule each run
- `DOC_TYPE_MISMATCH` rates tracked and trended; top `validation_reason` values reported

### M2 — Citation target resolver v1
**Deliverables**
- Citation extraction + normalization + mapping integrated
- Confidence policy implemented and reported
- Cache persisted across runs; cache hit-rate reported

**DoD gate**
- ≥ 90% of successful rows have ≥ 1 resolved Phase-1 case target
- Resolver ambiguity tracked and measurable (`excluded_reason=low_confidence_or_ambiguous`)

### M3 — Baseline models + evaluation harness
**Deliverables**
- Baseline 0: popularity
- Baseline 1: BM25/lexical retrieval
- Baseline 2: dense retrieval (or hybrid)
- Metrics dashboard/report per split + stratified reporting

**DoD gate**
- Leakage checks enforced (masked citations; dedupe split)
- Targets met: Recall@10 ≥ 0.10 and MRR@10 ≥ 0.05 (baseline 1)
- Stratified reporting by label-cardinality bins, source_system, needs_ocr (and document_type if applicable)
- Popularity-dominance check reported; flag regressions to “frequency-only” behavior

### M4 — Beta modeling iteration
**Deliverables**
- Improved reranker/hybrid approach
- Ablation study and error analysis
- Budget/cost report (OCR + resolver usage) for the build

**DoD gate**
- Beats baseline 1 on Recall@10 by +10% relative
- Risk posture reviewed (cost, API limits, leakage, exclusion rates)

---

## Sprint-level plan (example mapping)

**Sprint 1**
- Implement Dataset Inclusion Policy gates + deterministic doc-type validation
- Standardize `needs_ocr` decision module; integrate into extraction backends
- Build manifest + deterministic `build_id`
- Failure taxonomy end-to-end coverage

**Sprint 2**
- Facts span extraction stabilization + hard-PDF regression suite
- Local citation extraction + normalization; begin resolver integration
- Start Gold Audit Set process (rubric + sampling tool)

**Sprint 3**
- Resolver confidence policy + caching + budgets (per build_id)
- Train/eval splits with dedupe controls
- First audit readout integrated into weekly dashboard

**Sprint 4**
- Baseline retrieval models + eval harness + leakage tests
- First stratified metrics readout; error analysis by bins

---

## Risk register

| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---:|---:|---|---|
| PDF quality variance (scans, bad encodings) | High | High | Standardize OCR routing; cache OCR outputs; regression suite on “hard PDFs”; track per-source failure rates | Data Eng |
| OCR compute/cost | Med | High | OCR only when needed; batching; caching; enforce weekly OCR budget; defer overflow with explicit markers | Infra/Data Eng |
| API limits/throttling | Med | Med | Local extraction first; send **normalized cites only**; chunking; persisted cache; backoff/jitter; enforce request budget per `build_id` | Infra |
| Label leakage (citations present in input) | High | High | Mask citations; dedupe splits; enforce leakage tests in eval harness; fail run on unmasked input | ML Eng |
| Citation ambiguity / noisy labels | Med | Med | Explicit target semantics; `target_type` + `excluded_reason`; confidence policy; unresolved bucket with audit trails | ML Eng/Data Eng |
| Doc-type noise (non-merits docs) | Med | High | Inclusion policy gates; deterministic validation; trend DOC_TYPE_MISMATCH + validation_reasons; report exclusion rates | Data Eng |
| Licensing/redistribution mistakes | Med | High | Decision tree + retention rules; separate internal vs publishable artifacts; governance sign-off before release | Governance/PM |
| Restricted/sealed docs | Low | High | Enforce inclusion policy rules; detect sealed/restricted markers; report exclusion rates by rule; block encrypted PDFs | Data Eng |

---

## Licensing / usage constraints (decision tree + retention rules) (v0.2)

This section is governance-ready. Defaults should be confirmed by the governance reviewer.

### Decision tree (by `source_system`)
1) **Court opinions from permissive bulk sources** (e.g., CourtListener bulk data, CAP)
- **Publishable-by-default (subject to source terms):**
  - opinion text, canonical IDs, citations, derived embeddings
- **Retention:** indefinite (as allowed), with provenance manifests.

2) **RECAP / PACER docket filings** (party-submitted briefs and other filings)
- **Default: internal-only**
  - raw PDFs, extracted full text, facts spans
- **Publishable-by-default artifacts (preferred):**
  - document identifiers/URLs (where permitted), SHA256 hashes, offsets, failure metrics, and **case-target labels** (canonical IDs) *without distributing brief text*
- **Retention (default):**
  - raw PDFs: 180 days (extend only if required for reproducibility or audit)
  - extracted text + facts spans: 180 days, access-controlled
  - derived labels/metrics/manifests: indefinite

3) **Unknown or mixed-license sources**
- Treat as RECAP defaults until clarified.
- Block publishing of text-derived artifacts pending review.

### Derived artifacts policy
- If an artifact contains substantial brief text (full text or facts span), treat as internal-only unless explicitly cleared.
- If an artifact contains only identifiers/hashes/labels/metrics, it is the default candidate for sharing.

### Required governance outputs per release
- Source inventory by `source_system`
- Publishable artifact list with justification
- Retention policy confirmation (windows + access controls)

---

## Stakeholder review schedule

### Weekly (execution)
- Pipeline health dashboard:
  - acquisition success, extraction success, OCR rate, facts span success, resolution success
  - exclusion rates by inclusion rule + DOC_TYPE_MISMATCH trend
  - failure taxonomy distribution (top 10 codes)
  - Gold Audit Set snapshot (latest build_id): facts correctness, resolution correctness, top failure patterns
- Decision log updates (schema changes, heuristic changes, resolver version changes)

### Biweekly (sprint review)
- Demo of pipeline improvements
- Updated acceptance thresholds status vs targets (including audit results)
- Risk register review (new risks, mitigations, ownership)
- Gold Audit Set readout (facts correctness, resolution correctness) + top failure patterns

### Monthly (governance)
- Licensing/redistribution posture review (decision tree confirmation)
- API usage and rate-limit compliance review + budget adherence
- Dataset publication readiness assessment (if applicable)
