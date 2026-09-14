# Gold Audit Set

100 documents sampled proportionally by (extractor_confidence x facts_length_bin).
Seed: 42. No bias toward any particular target count, doc type, or confidence level.

> **Span text is not tracked in git** (D9, 2026-09-14): full spans live in `data/processed/gold_audit_text.jsonl` (gitignored) and in `gold_audit_set.parquet`. This file keeps ids, metadata, ratings, and notes only.

## Audit Rubric

For each row, evaluate the **facts_text** span:
- **correct**: Span substantially captures narrative facts/background. Not dominated by argument, TOA/TOC, or boilerplate.
- **partially_correct**: Span captures some facts but includes significant non-facts content or misses key facts sections.
- **incorrect**: Span is mostly argument, TOC, boilerplate, or unrelated content.

---

### Document 1 (ID: 406937652)

| Field | Value |
|-------|-------|
| Search Result ID | 406937652 |
| Short Description | Brief |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 6,450 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_4_sections;no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.49e6c51e-1581-4b81-8f65-85a979f37aba/gov.uscourts.ca9.49e6c51e-1581-4b81-8f65-85a979f37aba.18.1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `6450` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 
- STATUTORY ADDENDUM STATEMENT inclusded in the facts section. Not sure whether or not we should include this as it is not a fact of the case even though it is a factual statement. 
- 
--- 

### Document 2 (ID: 442367351)

| Field | Value |
|-------|-------|
| Search Result ID | 442367351 |
| Short Description | Reply Brief |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 9,431 chars |
| Resolved Targets | 17 |
| Extractor Notes | no_exact_heading;fallback_pre_argument;toc_contamination;low_alpha_ratio |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca3.123730/gov.uscourts.ca3.123730.40.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `9431` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 3 (ID: 436358043)

| Field | Value |
|-------|-------|
| Search Result ID | 436358043 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 15,400 chars |
| Resolved Targets | 40 |
| Extractor Notes | merged_4_sections;toc_contamination;low_alpha_ratio;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca11.82976/gov.uscourts.ca11.82976.38.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `15400` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 4 (ID: 474122994)

| Field | Value |
|-------|-------|
| Search Result ID | 474122994 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 4,916 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_2_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca1.53833/gov.uscourts.ca1.53833.00108424223.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `4916` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 5 (ID: 433231234)

| Field | Value |
|-------|-------|
| Search Result ID | 433231234 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 5,968 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_4_sections;no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca11.83446/gov.uscourts.ca11.83446.39.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `5968` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 6 (ID: 434589334)

| Field | Value |
|-------|-------|
| Search Result ID | 434589334 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 12,656 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_5_sections;no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca2.cce79a3c-9d17-4627-86ed-3ea60824e833/gov.uscourts.ca2.cce79a3c-9d17-4627-86ed-3ea60824e833.22.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `12656` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 7 (ID: 408759558)

| Field | Value |
|-------|-------|
| Search Result ID | 408759558 |
| Short Description | Proposed Amicus Brief |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 13,759 chars |
| Resolved Targets | 17 |
| Extractor Notes | merged_2_sections;toc_contamination;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca1.51474/gov.uscourts.ca1.51474.108178777.2.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `13759` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 8 (ID: 447883469)

| Field | Value |
|-------|-------|
| Search Result ID | 447883469 |
| Short Description | Appendix Appellant's Appendix and Index Vol 1 |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 4,842 chars |
| Resolved Targets | 0 |
| Extractor Notes | merge_limit_warning;merged_6_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.cacd.967119/gov.uscourts.cacd.967119.18.1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `4842` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 9 (ID: 471288789)

| Field | Value |
|-------|-------|
| Search Result ID | 471288789 |
| Short Description | Brief |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 18,497 chars |
| Resolved Targets | 4 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.49dee411-3e06-4afb-9750-69e83c581444/gov.uscourts.ca9.49dee411-3e06-4afb-9750-69e83c581444.29.1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `18497` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 10 (ID: 462256028)

| Field | Value |
|-------|-------|
| Search Result ID | 462256028 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 15,212 chars |
| Resolved Targets | 3 |
| Extractor Notes | merged_2_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca11.92709/gov.uscourts.ca11.92709.81.0_1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `15212` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 11 (ID: 370036407)

| Field | Value |
|-------|-------|
| Search Result ID | 370036407 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 17,125 chars |
| Resolved Targets | 3 |
| Extractor Notes | merged_2_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.343497/gov.uscourts.ca9.343497.15.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `17125` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 12 (ID: 460576485)

| Field | Value |
|-------|-------|
| Search Result ID | 460576485 |
| Short Description | Amicus Curiae Brief |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 8,985 chars |
| Resolved Targets | 0 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca1.53125/gov.uscourts.ca1.53125.00108373517.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `8985` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 13 (ID: 288399491)

| Field | Value |
|-------|-------|
| Search Result ID | 288399491 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 49,701 chars |
| Resolved Targets | 10 |
| Extractor Notes | merged_4_sections;guardrail_truncated;toc_contamination;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.340823/gov.uscourts.ca9.340823.6.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `49701` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 14 (ID: 375535392)

| Field | Value |
|-------|-------|
| Search Result ID | 375535392 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 18,397 chars |
| Resolved Targets | 4 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.341794/gov.uscourts.ca9.341794.11.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `18397` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 15 (ID: 453186847)

| Field | Value |
|-------|-------|
| Search Result ID | 453186847 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 8,012 chars |
| Resolved Targets | 4 |
| Extractor Notes | merged_2_sections;toc_contamination |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca11.90254/gov.uscourts.ca11.90254.29.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `8012` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 16 (ID: 435087205)

| Field | Value |
|-------|-------|
| Search Result ID | 435087205 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 16,084 chars |
| Resolved Targets | 0 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.b83b0a6d-b161-4252-abaf-84b26c84d58f/gov.uscourts.ca9.b83b0a6d-b161-4252-abaf-84b26c84d58f.18.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `16084` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 17 (ID: 473510339)

| Field | Value |
|-------|-------|
| Search Result ID | 473510339 |
| Short Description | Reply Brief |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 1,945 chars |
| Resolved Targets | 0 |
| Extractor Notes | no_exact_heading;fallback_pre_argument |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca3.125902/gov.uscourts.ca3.125902.76.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `1945` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 18 (ID: 437893748)

| Field | Value |
|-------|-------|
| Search Result ID | 437893748 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 9,195 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_3_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.e758f379-2845-4531-9d36-0e2ed70b58a2/gov.uscourts.ca9.e758f379-2845-4531-9d36-0e2ed70b58a2.10.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `9195` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 19 (ID: 370027454)

| Field | Value |
|-------|-------|
| Search Result ID | 370027454 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 15,402 chars |
| Resolved Targets | 8 |
| Extractor Notes | merged_2_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.344453/gov.uscourts.ca9.344453.47.0_4.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `15402` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 20 (ID: 461880976)

| Field | Value |
|-------|-------|
| Search Result ID | 461880976 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 10,841 chars |
| Resolved Targets | 1 |
| Extractor Notes | guardrail_truncated |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca10.89906/gov.uscourts.ca10.89906.44.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `10841` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 21 (ID: 404319241)

| Field | Value |
|-------|-------|
| Search Result ID | 404319241 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 44,336 chars |
| Resolved Targets | 34 |
| Extractor Notes | merged_5_sections;toc_contamination;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.cafc.21253/gov.uscourts.cafc.21253.12.2.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `44336` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 22 (ID: 433849800)

| Field | Value |
|-------|-------|
| Search Result ID | 433849800 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 39,626 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_5_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca2.68a3715f-7801-40c1-b4b3-f082bb34f09a/gov.uscourts.ca2.68a3715f-7801-40c1-b4b3-f082bb34f09a.22.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `39626` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 23 (ID: 461700636)

| Field | Value |
|-------|-------|
| Search Result ID | 461700636 |
| Short Description | Appellant-Petitioner's Opening Brief |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 16,613 chars |
| Resolved Targets | 1 |
| Extractor Notes | merged_2_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca10.88830/gov.uscourts.ca10.88830.40.1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `16613` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 24 (ID: 315615384)

| Field | Value |
|-------|-------|
| Search Result ID | 315615384 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 10,894 chars |
| Resolved Targets | 16 |
| Extractor Notes | toc_contamination;low_alpha_ratio;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca11.80714/gov.uscourts.ca11.80714.42.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `10894` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 25 (ID: 457209487)

| Field | Value |
|-------|-------|
| Search Result ID | 457209487 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 5,887 chars |
| Resolved Targets | 0 |
| Extractor Notes | span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.c2ea3a48-bfad-4808-8f46-4f684117f880/gov.uscourts.ca9.c2ea3a48-bfad-4808-8f46-4f684117f880.35.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `5887` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 26 (ID: 353968046)

| Field | Value |
|-------|-------|
| Search Result ID | 353968046 |
| Short Description | Appellee Brief |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 31,110 chars |
| Resolved Targets | 38 |
| Extractor Notes | merged_3_sections;toc_contamination;low_alpha_ratio;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca11.82715/gov.uscourts.ca11.82715.50.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `31110` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 27 (ID: 433437006)

| Field | Value |
|-------|-------|
| Search Result ID | 433437006 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 29,751 chars |
| Resolved Targets | 0 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca2.cf9859d7-874b-4382-8bb3-80a2b5c322ec/gov.uscourts.ca2.cf9859d7-874b-4382-8bb3-80a2b5c322ec.41.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `29751` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 28 (ID: 437301686)

| Field | Value |
|-------|-------|
| Search Result ID | 437301686 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 12,173 chars |
| Resolved Targets | 10 |
| Extractor Notes | no_exact_heading;fallback_pre_argument;toc_contamination |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca1.52511/gov.uscourts.ca1.52511.00108268006.2.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `12173` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 29 (ID: 266140831)

| Field | Value |
|-------|-------|
| Search Result ID | 266140831 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 5,905 chars |
| Resolved Targets | 0 |
| Extractor Notes | no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.341373/gov.uscourts.ca9.341373.28.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `5905` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 30 (ID: 376972570)

| Field | Value |
|-------|-------|
| Search Result ID | 376972570 |
| Short Description | Appellant Brief |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 18,369 chars |
| Resolved Targets | 3 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca11.83683/gov.uscourts.ca11.83683.43.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `18369` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 31 (ID: 414873376)

| Field | Value |
|-------|-------|
| Search Result ID | 414873376 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 49,022 chars |
| Resolved Targets | 29 |
| Extractor Notes | span_too_short;no_exact_heading;fallback_pre_argument;guardrail_truncated;toc_co |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca1.50958/gov.uscourts.ca1.50958.108189780.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `49022` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 32 (ID: 432675802)

| Field | Value |
|-------|-------|
| Search Result ID | 432675802 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 15,959 chars |
| Resolved Targets | 1 |
| Extractor Notes | merged_3_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca10.89018/gov.uscourts.ca10.89018.38.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `15959` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 33 (ID: 430591608)

| Field | Value |
|-------|-------|
| Search Result ID | 430591608 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 39,022 chars |
| Resolved Targets | 19 |
| Extractor Notes | merged_3_sections;toc_contamination;low_alpha_ratio;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca11.88341/gov.uscourts.ca11.88341.26.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `39022` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 34 (ID: 467345791)

| Field | Value |
|-------|-------|
| Search Result ID | 467345791 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 39,181 chars |
| Resolved Targets | 26 |
| Extractor Notes | merged_4_sections;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.83ad79ee-efb1-4ed5-a808-8ba268b7a281/gov.uscourts.ca9.83ad79ee-efb1-4ed5-a808-8ba268b7a281.25.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `39181` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 35 (ID: 287745741)

| Field | Value |
|-------|-------|
| Search Result ID | 287745741 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 6,964 chars |
| Resolved Targets | 0 |
| Extractor Notes | no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.342026/gov.uscourts.ca9.342026.10.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `6964` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 36 (ID: 412502220)

| Field | Value |
|-------|-------|
| Search Result ID | 412502220 |
| Short Description | Amicus for Appellant/Petitioner Brief Filed |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 15,413 chars |
| Resolved Targets | 4 |
| Extractor Notes | no_exact_heading;fallback_pre_argument;toc_contamination |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.cadc.40768/gov.uscourts.cadc.40768.1208661570.1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `15413` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 37 (ID: 427151113)

| Field | Value |
|-------|-------|
| Search Result ID | 427151113 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 22,955 chars |
| Resolved Targets | 1 |
| Extractor Notes | merged_3_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.68f6c7f0-a957-436e-8476-73adfa8dc314/gov.uscourts.ca9.68f6c7f0-a957-436e-8476-73adfa8dc314.6.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `22955` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 38 (ID: 470940051)

| Field | Value |
|-------|-------|
| Search Result ID | 470940051 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 3,188 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_4_sections;span_too_short;no_exact_heading;fallback_pre_argument;low_alph |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca2.63b922d9-38ae-4798-9019-2431456adaba/gov.uscourts.ca2.63b922d9-38ae-4798-9019-2431456adaba.29.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `3188` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 39 (ID: 452597360)

| Field | Value |
|-------|-------|
| Search Result ID | 452597360 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 20,864 chars |
| Resolved Targets | 10 |
| Extractor Notes | span_too_short;no_exact_heading;fallback_pre_argument;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca4.179603/gov.uscourts.ca4.179603.21.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `20864` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 40 (ID: 376396029)

| Field | Value |
|-------|-------|
| Search Result ID | 376396029 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 5,061 chars |
| Resolved Targets | 0 |
| Extractor Notes | no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca2.59931/gov.uscourts.ca2.59931.89.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `5061` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 41 (ID: 223341867)

| Field | Value |
|-------|-------|
| Search Result ID | 223341867 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 15,982 chars |
| Resolved Targets | 6 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca6.145366/gov.uscourts.ca6.145366.27.0_1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `15982` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 42 (ID: 446147487)

| Field | Value |
|-------|-------|
| Search Result ID | 446147487 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 5,566 chars |
| Resolved Targets | 5 |
| Extractor Notes | span_ends_very_late |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.51fc2b15-8193-40ab-9ac0-c06b8c86c68c/gov.uscourts.ca9.51fc2b15-8193-40ab-9ac0-c06b8c86c68c.71.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `5566` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 43 (ID: 470584236)

| Field | Value |
|-------|-------|
| Search Result ID | 470584236 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 5,545 chars |
| Resolved Targets | 0 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca11.93612/gov.uscourts.ca11.93612.33.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `5545` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 44 (ID: 437133081)

| Field | Value |
|-------|-------|
| Search Result ID | 437133081 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 19,015 chars |
| Resolved Targets | 0 |
| Extractor Notes | no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.cafc.22615/gov.uscourts.cafc.22615.13.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `19015` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 45 (ID: 431833857)

| Field | Value |
|-------|-------|
| Search Result ID | 431833857 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 8,178 chars |
| Resolved Targets | 0 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.b1f4d31c-3797-43be-a21c-ce67e8392d80/gov.uscourts.ca9.b1f4d31c-3797-43be-a21c-ce67e8392d80.7.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `8178` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 46 (ID: 292743167)

| Field | Value |
|-------|-------|
| Search Result ID | 292743167 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 6,502 chars |
| Resolved Targets | 13 |
| Extractor Notes | toc_contamination;low_alpha_ratio;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca3.118238/gov.uscourts.ca3.118238.23.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `6502` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 47 (ID: 412079849)

| Field | Value |
|-------|-------|
| Search Result ID | 412079849 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 10,746 chars |
| Resolved Targets | 0 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.848c2001-e956-4db1-9682-649aab05b816/gov.uscourts.ca9.848c2001-e956-4db1-9682-649aab05b816.13.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `10746` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 48 (ID: 408697647)

| Field | Value |
|-------|-------|
| Search Result ID | 408697647 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 16,591 chars |
| Resolved Targets | 8 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca6.151615/gov.uscourts.ca6.151615.34.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `16591` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 49 (ID: 436418162)

| Field | Value |
|-------|-------|
| Search Result ID | 436418162 |
| Short Description |  |
| Doc Type | MERITS_SCOTUS |
| Confidence | low |
| Facts Length | 37,392 chars |
| Resolved Targets | 24 |
| Extractor Notes | span_too_short;no_exact_heading;fallback_pre_argument;toc_contamination;span_sta |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca4.178115/gov.uscourts.ca4.178115.35.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `37392` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 50 (ID: 415559487)

| Field | Value |
|-------|-------|
| Search Result ID | 415559487 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 13,302 chars |
| Resolved Targets | 1 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.bd9bcbc6-961b-4f27-9d18-a59caaecf661/gov.uscourts.ca9.bd9bcbc6-961b-4f27-9d18-a59caaecf661.9.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `13302` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 51 (ID: 404296837)

| Field | Value |
|-------|-------|
| Search Result ID | 404296837 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 9,832 chars |
| Resolved Targets | 31 |
| Extractor Notes | no_exact_heading;fallback_pre_argument;toc_contamination;low_alpha_ratio |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca11.85147/gov.uscourts.ca11.85147.70.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `9832` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 52 (ID: 471279807)

| Field | Value |
|-------|-------|
| Search Result ID | 471279807 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 620 chars |
| Resolved Targets | 0 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.7f5fec58-66d2-4c80-85eb-e2edf11c16ac/gov.uscourts.ca9.7f5fec58-66d2-4c80-85eb-e2edf11c16ac.12.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `620` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 53 (ID: 436047002)

| Field | Value |
|-------|-------|
| Search Result ID | 436047002 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 24,983 chars |
| Resolved Targets | 1 |
| Extractor Notes | merged_2_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.0ce1442d-7e76-46ed-8be9-4d43b9001dd5/gov.uscourts.ca9.0ce1442d-7e76-46ed-8be9-4d43b9001dd5.12.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `24983` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 54 (ID: 379031415)

| Field | Value |
|-------|-------|
| Search Result ID | 379031415 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 11,700 chars |
| Resolved Targets | 0 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.341906/gov.uscourts.ca9.341906.14.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `11700` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 55 (ID: 413679775)

| Field | Value |
|-------|-------|
| Search Result ID | 413679775 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 27,890 chars |
| Resolved Targets | 5 |
| Extractor Notes | merged_2_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.7865f97e-0fed-4179-976b-cb031005592b/gov.uscourts.ca9.7865f97e-0fed-4179-976b-cb031005592b.11.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `27890` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 56 (ID: 354358272)

| Field | Value |
|-------|-------|
| Search Result ID | 354358272 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 15,759 chars |
| Resolved Targets | 3 |
| Extractor Notes | merged_2_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.343994/gov.uscourts.ca9.343994.7.0_1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `15759` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 57 (ID: 472133187)

| Field | Value |
|-------|-------|
| Search Result ID | 472133187 |
| Short Description | Appellee/Respondent Brief Filed |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 5,531 chars |
| Resolved Targets | 0 |
| Extractor Notes | no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca5.226415/gov.uscourts.ca5.226415.49.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `5531` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 58 (ID: 444867540)

| Field | Value |
|-------|-------|
| Search Result ID | 444867540 |
| Short Description | Opening Brief (excluding Direct Criminal Cases) |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 24,780 chars |
| Resolved Targets | 1 |
| Extractor Notes | merged_5_sections;no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca3.124030/gov.uscourts.ca3.124030.27.1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `24780` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 59 (ID: 472377864)

| Field | Value |
|-------|-------|
| Search Result ID | 472377864 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 1,568 chars |
| Resolved Targets | 0 |
| Extractor Notes | no_exact_heading;fallback_pre_argument;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.0afabc25-e712-4d58-9dd8-36c93fd2b05d/gov.uscourts.ca9.0afabc25-e712-4d58-9dd8-36c93fd2b05d.36.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `1568` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 60 (ID: 474721568)

| Field | Value |
|-------|-------|
| Search Result ID | 474721568 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 16,068 chars |
| Resolved Targets | 0 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.7645411c-a96e-439a-86b0-dc56898a1a50/gov.uscourts.ca9.7645411c-a96e-439a-86b0-dc56898a1a50.30.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `16068` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 61 (ID: 406588147)

| Field | Value |
|-------|-------|
| Search Result ID | 406588147 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 12,264 chars |
| Resolved Targets | 11 |
| Extractor Notes | merged_2_sections;toc_contamination;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.10db6da7-826a-4f62-9458-72fa7a760b34/gov.uscourts.ca9.10db6da7-826a-4f62-9458-72fa7a760b34.11.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `12264` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 62 (ID: 415033942)

| Field | Value |
|-------|-------|
| Search Result ID | 415033942 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 9,977 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_2_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca2.cbd9d991-7b75-4519-ac03-751cb744362e/gov.uscourts.ca2.cbd9d991-7b75-4519-ac03-751cb744362e.49.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `9977` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 63 (ID: 470431781)

| Field | Value |
|-------|-------|
| Search Result ID | 470431781 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 5,766 chars |
| Resolved Targets | 0 |
| Extractor Notes | no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.9fc03734-91fc-46b5-a8bf-a51e67bd6709/gov.uscourts.ca9.9fc03734-91fc-46b5-a8bf-a51e67bd6709.53.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `5766` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 64 (ID: 413446772)

| Field | Value |
|-------|-------|
| Search Result ID | 413446772 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 35,353 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_2_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca11.82218/gov.uscourts.ca11.82218.26.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `35353` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 65 (ID: 435506124)

| Field | Value |
|-------|-------|
| Search Result ID | 435506124 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 1,520 chars |
| Resolved Targets | 0 |
| Extractor Notes | span_ends_very_late |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.53f7d746-d341-4903-8220-8dcd10315fc0/gov.uscourts.ca9.53f7d746-d341-4903-8220-8dcd10315fc0.44.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `1520` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 66 (ID: 473432953)

| Field | Value |
|-------|-------|
| Search Result ID | 473432953 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 49,972 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_4_sections;guardrail_truncated |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.cafc.22382/gov.uscourts.cafc.22382.19.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `49972` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 67 (ID: 451805507)

| Field | Value |
|-------|-------|
| Search Result ID | 451805507 |
| Short Description | Appellant-Petitioner Brief FILED |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 2,213 chars |
| Resolved Targets | 0 |
| Extractor Notes | no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca2.93a7d5a9-0a63-45b8-ba87-ee3e23621987/gov.uscourts.ca2.93a7d5a9-0a63-45b8-ba87-ee3e23621987.23.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `2213` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 68 (ID: 377375701)

| Field | Value |
|-------|-------|
| Search Result ID | 377375701 |
| Short Description | Brief |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 11,447 chars |
| Resolved Targets | 18 |
| Extractor Notes | merged_2_sections;toc_contamination;low_alpha_ratio;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.nvd.164395/gov.uscourts.nvd.164395.12.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `11447` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 69 (ID: 416100843)

| Field | Value |
|-------|-------|
| Search Result ID | 416100843 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 4,761 chars |
| Resolved Targets | 0 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.02889842-5503-4921-ac28-561d764c7462/gov.uscourts.ca9.02889842-5503-4921-ac28-561d764c7462.14.0_1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `4761` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 70 (ID: 469996466)

| Field | Value |
|-------|-------|
| Search Result ID | 469996466 |
| Short Description | Proposed Amicus Brief |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 14,542 chars |
| Resolved Targets | 38 |
| Extractor Notes | no_exact_heading;fallback_pre_argument;toc_contamination;low_alpha_ratio |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca1.51430/gov.uscourts.ca1.51430.00108408770.2.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `14542` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 71 (ID: 434759144)

| Field | Value |
|-------|-------|
| Search Result ID | 434759144 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 32,665 chars |
| Resolved Targets | 4 |
| Extractor Notes | merged_3_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca6.153885/gov.uscourts.ca6.153885.23.0_1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `32665` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 72 (ID: 356087086)

| Field | Value |
|-------|-------|
| Search Result ID | 356087086 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 48,457 chars |
| Resolved Targets | 39 |
| Extractor Notes | merged_6_sections;toc_contamination;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.342581/gov.uscourts.ca9.342581.11.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `48457` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 73 (ID: 474687769)

| Field | Value |
|-------|-------|
| Search Result ID | 474687769 |
| Short Description | Amicus for Appellant/Petitioner Brief Filed |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 3,348 chars |
| Resolved Targets | 2 |
| Extractor Notes | no_exact_heading;fallback_pre_argument;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.cadc.42183/gov.uscourts.cadc.42183.2167065.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `3348` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 74 (ID: 447945845)

| Field | Value |
|-------|-------|
| Search Result ID | 447945845 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 12,103 chars |
| Resolved Targets | 1 |
| Extractor Notes | merged_2_sections;no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.343008/gov.uscourts.ca9.343008.21.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `12103` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 75 (ID: 470371595)

| Field | Value |
|-------|-------|
| Search Result ID | 470371595 |
| Short Description | Abbreviated Record |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 49,935 chars |
| Resolved Targets | 19 |
| Extractor Notes | guardrail_truncated |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca1.53896/gov.uscourts.ca1.53896.00108410429.1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `49935` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 76 (ID: 432851731)

| Field | Value |
|-------|-------|
| Search Result ID | 432851731 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 446 chars |
| Resolved Targets | 0 |
| Extractor Notes | span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.46f350d3-89b4-481e-a0d2-5a9ba37ea230/gov.uscourts.ca9.46f350d3-89b4-481e-a0d2-5a9ba37ea230.15.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `446` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 77 (ID: 467141933)

| Field | Value |
|-------|-------|
| Search Result ID | 467141933 |
| Short Description |  |
| Doc Type | MERITS_SCOTUS |
| Confidence | medium |
| Facts Length | 21,562 chars |
| Resolved Targets | 0 |
| Extractor Notes | merge_limit_warning;merged_6_sections;no_citations_in_facts;span_starts_very_ear |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca4.180631/gov.uscourts.ca4.180631.51.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `21562` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 78 (ID: 438935114)

| Field | Value |
|-------|-------|
| Search Result ID | 438935114 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 31,819 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_3_sections;no_citations_in_facts;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.cafc.21736/gov.uscourts.cafc.21736.17.0_2.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `31819` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 79 (ID: 465752278)

| Field | Value |
|-------|-------|
| Search Result ID | 465752278 |
| Short Description | Amicus Curiae Brief (FRAP 29) |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 5,344 chars |
| Resolved Targets | 0 |
| Extractor Notes | no_exact_heading;fallback_pre_argument;toc_contamination |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca1.53019/gov.uscourts.ca1.53019.00108393122.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `5344` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 80 (ID: 453058564)

| Field | Value |
|-------|-------|
| Search Result ID | 453058564 |
| Short Description | Brief |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 14,745 chars |
| Resolved Targets | 0 |
| Extractor Notes | no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.ee4bf357-493d-46e4-884c-d09000abf652/gov.uscourts.ca9.ee4bf357-493d-46e4-884c-d09000abf652.8.1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `14745` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 81 (ID: 471216528)

| Field | Value |
|-------|-------|
| Search Result ID | 471216528 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 1,361 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_2_sections;low_alpha_ratio;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.57485409-980d-433a-b5ff-41cdc3c00aa2/gov.uscourts.ca9.57485409-980d-433a-b5ff-41cdc3c00aa2.8.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `1361` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 82 (ID: 316491830)

| Field | Value |
|-------|-------|
| Search Result ID | 316491830 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 30,340 chars |
| Resolved Targets | 1 |
| Extractor Notes | merged_2_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca2.59855/gov.uscourts.ca2.59855.70.0_1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `30340` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 83 (ID: 447173943)

| Field | Value |
|-------|-------|
| Search Result ID | 447173943 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 28,693 chars |
| Resolved Targets | 22 |
| Extractor Notes | span_too_short;no_exact_heading;fallback_pre_argument;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.ac49baa8-8388-470c-bb92-db8bdfedabb3/gov.uscourts.ca9.ac49baa8-8388-470c-bb92-db8bdfedabb3.29.0_1.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `28693` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 84 (ID: 430735069)

| Field | Value |
|-------|-------|
| Search Result ID | 430735069 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 3,418 chars |
| Resolved Targets | 0 |
| Extractor Notes | no_citations_in_facts;span_ends_very_late |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca1.52511/gov.uscourts.ca1.52511.00108249630.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `3418` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 85 (ID: 424072807)

| Field | Value |
|-------|-------|
| Search Result ID | 424072807 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 6,769 chars |
| Resolved Targets | 0 |
| Extractor Notes | no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.bea5dc3e-3a1f-466d-8a92-bba54d278acc/gov.uscourts.ca9.bea5dc3e-3a1f-466d-8a92-bba54d278acc.23.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `6769` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 86 (ID: 366442062)

| Field | Value |
|-------|-------|
| Search Result ID | 366442062 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 8,899 chars |
| Resolved Targets | 1 |
| Extractor Notes | merged_3_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.cafc.19982/gov.uscourts.cafc.19982.32.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `8899` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 87 (ID: 408208976)

| Field | Value |
|-------|-------|
| Search Result ID | 408208976 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 19,617 chars |
| Resolved Targets | 3 |
| Extractor Notes | merged_2_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.027ab3c5-2f89-44f6-8313-3adc82ff2b44/gov.uscourts.ca9.027ab3c5-2f89-44f6-8313-3adc82ff2b44.8.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `19617` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 88 (ID: 352204404)

| Field | Value |
|-------|-------|
| Search Result ID | 352204404 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 2,487 chars |
| Resolved Targets | 0 |
| Extractor Notes | no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.cafc.19768/gov.uscourts.cafc.19768.10.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `2487` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 89 (ID: 271105015)

| Field | Value |
|-------|-------|
| Search Result ID | 271105015 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 28,518 chars |
| Resolved Targets | 1 |
| Extractor Notes | merged_4_sections;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.340194/gov.uscourts.ca9.340194.20.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `28518` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 90 (ID: 391927398)

| Field | Value |
|-------|-------|
| Search Result ID | 391927398 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 17,336 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_3_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.cafc.20941/gov.uscourts.cafc.20941.12.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `17336` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 91 (ID: 456738575)

| Field | Value |
|-------|-------|
| Search Result ID | 456738575 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 6,031 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_2_sections;no_citations_in_facts |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca11.91706/gov.uscourts.ca11.91706.20.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `6031` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 92 (ID: 371220260)

| Field | Value |
|-------|-------|
| Search Result ID | 371220260 |
| Short Description | Appellant Brief |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 18,894 chars |
| Resolved Targets | 25 |
| Extractor Notes | merged_4_sections;toc_contamination;low_alpha_ratio;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca11.81242/gov.uscourts.ca11.81242.31.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `18894` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 93 (ID: 419758728)

| Field | Value |
|-------|-------|
| Search Result ID | 419758728 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 1,884 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_3_sections;low_alpha_ratio;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca2.e869d071-5cf3-47e7-9c63-ad5073569f39/gov.uscourts.ca2.e869d071-5cf3-47e7-9c63-ad5073569f39.30.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `1884` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 94 (ID: 469905475)

| Field | Value |
|-------|-------|
| Search Result ID | 469905475 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 13,586 chars |
| Resolved Targets | 37 |
| Extractor Notes | no_exact_heading;fallback_pre_argument;toc_contamination;low_alpha_ratio |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca11.92709/gov.uscourts.ca11.92709.126.0_3.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `13586` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 95 (ID: 466139790)

| Field | Value |
|-------|-------|
| Search Result ID | 466139790 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | medium |
| Facts Length | 16,643 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_2_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.22314/gov.uscourts.ca9.22314.8.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `16643` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 96 (ID: 384087868)

| Field | Value |
|-------|-------|
| Search Result ID | 384087868 |
| Short Description | Amicus Curiae Brief Filed |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 1,427 chars |
| Resolved Targets | 0 |
| Extractor Notes | toc_contamination;span_starts_very_early |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca5.216848/gov.uscourts.ca5.216848.96.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `1427` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 97 (ID: 216664791)

| Field | Value |
|-------|-------|
| Search Result ID | 216664791 |
| Short Description | Exhibit 2 -Appellants' Opening Brief in Generali |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 15,317 chars |
| Resolved Targets | 0 |
| Extractor Notes |  |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.nysd.575404/gov.uscourts.nysd.575404.37.2.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `15317` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 98 (ID: 445583117)

| Field | Value |
|-------|-------|
| Search Result ID | 445583117 |
| Short Description | Declaration |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 49,301 chars |
| Resolved Targets | 0 |
| Extractor Notes | merged_3_sections;guardrail_truncated |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.dcd.279032/gov.uscourts.dcd.279032.146.3.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `49301` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 99 (ID: 436570273)

| Field | Value |
|-------|-------|
| Search Result ID | 436570273 |
| Short Description |  |
| Doc Type | UNKNOWN |
| Confidence | low |
| Facts Length | 6,379 chars |
| Resolved Targets | 0 |
| Extractor Notes | merge_limit_warning;merged_6_sections;low_alpha_ratio |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca2.b519d1e6-6298-4652-8b45-d873f09f6a8a/gov.uscourts.ca2.b519d1e6-6298-4652-8b45-d873f09f6a8a.53.0.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `6379` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---

### Document 100 (ID: 409379976)

| Field | Value |
|-------|-------|
| Search Result ID | 409379976 |
| Short Description | Brief |
| Doc Type | UNKNOWN |
| Confidence | high |
| Facts Length | 24,279 chars |
| Resolved Targets | 5 |
| Extractor Notes | merged_2_sections |
| PDF URL | https://storage.courtlistener.com/recap/gov.uscourts.ca9.194653ec-9560-4d39-af1a-202da8fba7de/gov.uscourts.ca9.194653ec-9560-4d39-af1a-202da8fba7de.22.1_2.pdf |

**Extracted Facts Span:** text not tracked (see `data/processed/gold_audit_text.jsonl`, regenerable from `data/processed/gold_audit_set.parquet`; `24279` chars).

**Rating:** `___________` (correct / partially_correct / incorrect)

**Notes:** 

---
