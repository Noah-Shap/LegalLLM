# Gold set labeling guide (v1)

Applies to `evals/gold/gold_v1.jsonl`. One annotator (Noah) for Phase 1; the ambiguity rules below are the
inter-annotator agreement we would hand a second labeler. Every label is a judgment about **one specific span of
one specific text**: the offsets refer to `preprocess_text(normalize_text(pdf_text))`, exactly what
`legallm-extract` shows, and `doc_sha1` pins that text.

## What you are labeling

| Record source | n | Task |
|---|---:|---|
| `audit_set` (`g001`–`g100`) | 100 | Rate the rules_v2 span with the rubric. Correct the boundaries on **at least 40**, biased to `low`/`medium` confidence. |
| `no_facts_span` (`f001`–`f020`) | 20 | rules_v2 found nothing. Locate the facts section by hand (gold span), or mark `has_facts = no`. |

## Rubric (rating of the rules_v2 span)

- **correct** — the span substantially captures the narrative facts / background and is not dominated by
  argument, table of contents / authorities, or boilerplate. Small imperfections at the edges (a heading line,
  one stray sentence, a page-header stamp) are still *correct*.
- **partially_correct** — the span captures real facts **but** either (a) includes a significant block of
  non-facts content (argument, TOC, cover page, certificate) or (b) misses a facts subsection it should include.
  Rule of thumb: more than ~10 % of the span is wrong, or a whole facts subsection is missing.
- **incorrect** — mostly argument, TOC, boilerplate, or unrelated content; or the brief's real facts section is
  elsewhere.

Rate the span as extracted. Do not let a good boundary correction upgrade the rating.

## Boundary rules (what the gold span includes)

1. **Start** at the first body sentence of the facts narrative. Exclude the section heading line
   ("STATEMENT OF FACTS", "I. Factual Background") and anything before it.
2. **End** at the last sentence before the next non-facts heading (ARGUMENT, SUMMARY OF ARGUMENT, STANDARD OF
   REVIEW, DISCUSSION, ANALYSIS, CONCLUSION). Exclude that heading.
3. **Include** adjacent factual subsections that share the narrative: Factual Background + Procedural
   Background / Procedural History / Course of Proceedings / Nature of the Case, and their sub-headings.
4. **INTRODUCTION / PRELIMINARY STATEMENT**: include only when it is a factual summary rather than argument.
   Federal appellate opening/response briefs: usually argumentative → exclude. Cert petitions, SCOTUS merits
   briefs, district-court briefs: usually factual → include. When mixed, exclude and note it.
5. **Statement of the case** that combines facts and procedure → include the whole section.
6. **Footnotes, record cites ("1-ER-102"), and page-header stamps** inside the span stay in (they are part of the
   text; the extractor is not expected to strip them).
7. **Statutory addenda / "pertinent provisions" paragraphs** placed before the facts heading → exclude (these
   are not facts of the case). This is the open question from the first audit note on `g001`; the rule is
   "exclude, note it".
8. **Questions Presented / Jurisdictional Statement / Standard of Review** → never part of the facts span.
9. **OCR noise**: if the text is garbled but the section is identifiable, label it and add note `ocr_noise`.
   If it is unreadable, `has_facts = yes`, no gold span, note `unreadable`.

## `no_facts_span` records

- If the brief has a facts / background narrative, locate it (anchors or offsets) and save the gold span with
  `has_facts = yes`. Add a note naming the heading the rules missed (e.g. "heading was 'BACKGROUND FACTS' in
  title case").
- If the document has no facts narrative (motion, reply, appendix, letter, transcript), set `has_facts = no`
  and note the document type.

## Ambiguity rules (decide the same way every time)

- A facts section split by an intervening non-facts heading (e.g. facts → SUMMARY OF ARGUMENT → more facts):
  gold span = the **first** contiguous block; note `split_facts`.
- Reply briefs with a short "Statement" that mostly rebuts: `has_facts = yes` only if it narrates events; else
  `has_facts = no`, note `reply_no_narrative`.
- **Reply briefs, amicus briefs, declarations/appendices, motion replies** (the first LLM run flags 17 of the
  100 audit docs as such): `has_facts = no` unless there is a genuine narrative section (Statement of Facts /
  Background / Statement of the Case). An argumentative INTRODUCTION or an "Interest of Amici" section is
  not a facts section. Rate the rules span `incorrect` when it is a fallback slice of such a document.
- Attached opinions, reports and recommendations, or exhibits inside a filing are **not** the brief's facts
  section (`has_facts = no`, note `attachment_only`), unless the filing itself is the brief.
- When the rules span is off by only the heading line or one sentence at an edge, still record the corrected
  boundaries (cheap, and it feeds the IoU metric), but rate **correct**.
- Never widen a span to "be safe". The eval rewards precision as much as recall.

## Mechanics

```bash
pip install -e ".[label]"
legallm-gold stats                  # progress
legallm-gold label                  # Streamlit UI on http://localhost:8501
legallm-gold verify                 # after labeling: spans in bounds, doc_sha1 unchanged
```

In the UI: read the rules span preview → pick a rating → if correcting, paste the verbatim first words of the
facts body as the start anchor and the verbatim last words as the end anchor, press **Locate anchors**, check
the preview, fine-tune the offsets if needed → **Save & next**. Commit `gold_v1.jsonl` at the end of each
session (`git commit -m "data(gold): label session N"`).
