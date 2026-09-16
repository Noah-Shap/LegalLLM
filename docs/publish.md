# Publish kit (C17) — drafts for Noah

Everything here is a draft for Noah to edit and post; nothing is published from the repo.

## LinkedIn post (≈ 180 words)

I replaced a rule-based extractor with an LLM and built the evals to prove it was worth it.

The task: pull the Statement of Facts out of U.S. court briefs — the span plus parties, posture, dated events and
citations — as validated JSON. The old heuristic found a span on 83 % of documents and looked fine on the
pipeline's downstream metric.

What the evals showed:
• Span accuracy vs a 120-doc gold set: 0.57 → 0.98 IoU (rules → routed Claude). 96 % of documents within 0.9.
• The old "citation resolution rate" was rewarding leakage: only 15 % of the citations the rules resolved were in
  the facts section. The LLM's were 96 % precise.
• Retrieval didn't move at all — even with human gold spans. Better extraction isn't the bottleneck there; the
  retriever is. Stated, not hidden.
• Routing 7 % of documents to a stronger model fixed the last failure class for +$0.06/doc.

An Opus judge pre-labeled everything; I reviewed the hard third and got κ 0.89, so the judge earned its place.
CI replays frozen model outputs and fails on a 2-point IoU drop.

Repo, results table, failure taxonomy and the tradeoffs write-up: <link>. Demo: <space link>.

## 60-second demo script

| t | screen | say |
|---|---|---|
| 0–8 s | README results table | "Rules baseline vs the LLM extractor on 120 labeled briefs — span IoU 0.57 to 0.98." |
| 8–25 s | Streamlit UI: upload a brief, method llm-v3 | "Upload a brief. Left: the rule-based span, which starts on the table of contents. Right: the LLM span, plus parties, posture, events, citations — every citation checked against the source text." |
| 25–38 s | provenance line: tier / trigger / cost | "This one stayed on the cheap tier. When Sonnet can't locate its own anchors, it escalates to Opus — 8 of 120 documents, all recovered." |
| 38–50 s | evals/RESULTS.md downstream section | "The surprise: the old resolution metric was leakage. And retrieval didn't improve even with gold spans — that's the next problem, not this one." |
| 50–60 s | GitHub Actions gate job summary (FAIL on the demo branch) | "Every PR replays frozen model outputs; a two-point IoU drop fails the build. Link in the description." |

## Repo publish checklist

- [x] Repo public (`github.com/Noah-Shap/LegalLLM`), README retitled, results + limitations + how-to-run
- [x] CI green on `main`; deliberately regressed branch fails the gate (`demo/gate-regression`)
- [ ] Hugging Face Space pushed with `ANTHROPIC_API_KEY` secret (Noah; see `deploy/README.md`) → paste URL into README "Live demo"
- [ ] LinkedIn post (above) with the two links
- [ ] 60-s demo recorded from the script above
