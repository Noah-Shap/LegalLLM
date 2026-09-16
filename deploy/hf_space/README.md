---
title: Legal Facts Extraction
emoji: ⚖️
colorFrom: gray
colorTo: blue
sdk: streamlit
sdk_version: "1.40.0"
app_file: app.py
pinned: false
license: mit
short_description: Statement-of-Facts extraction from U.S. court briefs — rules baseline vs Claude, with validators
---

# Legal facts extraction — demo

Upload a U.S. court brief (PDF or text) and see the **Statement of Facts** span plus structured fields
(parties, procedural posture, key events, citations) extracted by a Claude-based extractor, side by side with the
rule-based baseline, with deterministic validator flags (span integrity, citation fidelity, prompt-injection guard).

- `rules_v2` runs without any model and is always available.
- `llm-v5` (default) = Sonnet 5 first, escalated to Opus 5 when the cheap pass cannot locate its own anchors, with
  record citations returned as printed plus their page list; `llm-v3` is the faster span-focused route. Both need
  the `ANTHROPIC_API_KEY` secret on this Space.
- Requests are capped per session; document text is never logged.

Source, evals and results: <https://github.com/Noah-Shap/LegalLLM>.
