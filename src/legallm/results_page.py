"""Curated results page (evals/RESULTS.md) rendered from an extraction-eval run directory.

    legallm-xeval --render evals/runs/<run_id> [--results-out evals/RESULTS.md]

The run report (report.md) is exhaustive; this page is the one a reader of the
README should see: methods, headline table, agreement, per-source view, field
coverage, and how to read the numbers. It states plainly when gold labels are
missing so operational numbers are not mistaken for accuracy.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _pct(x: Any) -> str:
    return "—" if x is None else f"{x:.1%}"


def _num(x: Any, nd: int = 3) -> str:
    return "—" if x is None else f"{x:.{nd}f}"


def _money(x: Any) -> str:
    return "—" if x is None else f"${x:.3f}"


HEADLINE: list[tuple[str, Callable[[dict[str, Any]], str]]] = [
    ("IoU vs gold (mean)", lambda s: _num(s["iou_mean"])),
    ("IoU ≥ 0.9 (share of labeled docs)", lambda s: _pct(s["iou_ge_0.9"])),
    ("span found", lambda s: _pct(s["span_found_rate"])),
    ("validator pass", lambda s: _pct(s["validation_pass_rate"])),
    ("citation fidelity, verbatim (mean)", lambda s: _num(s["citation_fidelity_mean"])),
    ("citation support, verbatim + components (mean)", lambda s: _num(s.get("citation_support_mean"))),
    (
        "cites emitted / non-verbatim / unsupported",
        lambda s: (
            f"{s.get('n_cites_emitted', '—')} / {s.get('n_cites_nonverbatim', '—')} / "
            f"{s.get('n_cites_unsupported', '—')}"
        ),
    ),
    ("docs with unsupported cites", lambda s: f"{s['docs_with_unsupported_cites']}/{s['n_docs_with_cites']}"),
    ("recovered span, failure stratum", lambda s: f"{_pct(s['recovered_span_rate'])} (n={s['failure_stratum_n']})"),
    (
        "IoU auto-rating ↔ label rating (label rates the rules span; rules_v2 row only)",
        lambda s: (
            f"{_pct(s['auto_vs_human_agreement'])} (n={s['auto_vs_human_n']})"
            if s.get("method") == "rules_v2"
            else "n/a"
        ),
    ),
    ("cost / doc", lambda s: _money(s["cost_usd_per_doc"])),
    ("latency / doc (mean)", lambda s: f"{_num(s['latency_s_mean'], 2)} s"),
]

FIELDS: list[tuple[str, str, bool]] = [
    ("parties non-empty", "parties_nonempty_rate", True),
    ("procedural posture present", "posture_rate", True),
    ("key events / doc (mean)", "key_events_mean", False),
    ("record cites / doc (mean)", "record_cites_mean", False),
    ("case cites / doc (mean)", "case_cites_mean", False),
]


def _gold_desc(meta: dict[str, Any]) -> str:
    n, h, j = meta["n_gold"], meta.get("n_gold_human"), meta.get("n_gold_judge")
    if h is None or j is None:
        return f"{n} gold-labeled"
    return f"{n} gold-labeled: {h} human, {j} judge-accepted"


def _downstream_section(ds: dict[str, Any]) -> list[str]:
    """Headline rows from ``downstream.json`` (legallm-downstream): resolution + BM25 Recall@k per span source."""
    meta, S, B = ds["meta"], ds["summaries"], ds["baseline"]
    k = meta["k"]
    ms = meta["methods"]
    out: list[str] = []
    out.append("## Downstream: citation resolution and BM25 retrieval on each method's span")
    out.append("")
    out.append(
        f"Spans → case citations → resolver cache ({meta['cache_entries']} entries, no network) and → masked query "
        f"→ BM25 fitted on the build's train split minus the gold docs; targets fixed per doc (the gold span's "
        f"resolved citations). {meta['n_docs']} gold docs, {meta['n_queries']} retrieval queries. Build baseline "
        f"on its own test split: Recall@{k} {_num(B[f'recall@{k}'])} (n={B['n_test_queries']})."
    )
    out.append("")
    out.append("| metric | " + " | ".join(ms) + " |")
    out.append("|---|" + "---:|" * len(ms))
    rows: list[tuple[str, Callable[[dict[str, Any]], str]]] = [
        ("docs with ≥ 1 resolved citation", lambda s: _pct(s["docs_resolved_ge1_rate"])),
        (
            "resolved-target precision / recall vs gold span",
            lambda s: f"{_pct(s['target_precision'])} / {_pct(s['target_recall'])}",
        ),
        ("spurious targets on no-facts docs", lambda s: f"{s['spurious_target_docs']}/{s['n_nofacts_docs']} docs"),
        (f"BM25 Recall@{k} (n={S[ms[0]]['n_queries']})", lambda s: _num(s[f"recall@{k}"])),
        (f"BM25 MRR@{k}", lambda s: _num(s[f"mrr@{k}"])),
        (
            f"BM25 Recall@{k}, queries with a span",
            lambda s: f"{_num(s[f'recall@{k}_span_found'])} (n={s['n_queries_span_found']})",
        ),
    ]
    for name, fn in rows:
        out.append(f"| {name} | " + " | ".join(fn(S[m]) for m in ms) + " |")
    out.append("")
    out.append(f"Full downstream report: `{meta['run_dir']}/downstream.md`.")
    out.append("")
    return out


def render_results(run_dir: Path, *, gold_note: str | None = None) -> str:
    """Build the curated results page from ``<run_dir>/summary.json``."""
    run_dir = Path(run_dir)
    data = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    meta, summaries, strata = data["meta"], data["summaries"], data["strata"]
    agreements, comparisons = data.get("agreements", []), data.get("comparisons", [])
    methods = list(summaries)
    n_gold = meta["n_gold"]
    L: list[str] = []
    L.append("# Results — facts extraction: rules_v2 vs LLM")
    L.append("")
    L.append(
        f"Run `{meta['run_id']}` · gold `{meta['gold_path']}` · subset **{meta['subset']}** · "
        f"{meta['n_docs']} documents ({_gold_desc(meta)}) · {meta['timestamp'][:19]}Z"
    )
    L.append("")
    if n_gold == 0:
        L.append(
            "> **Labels pending.** No gold labels yet, so IoU-vs-gold, auto-rating agreement and the "
            "recovered-span rate are not available. Everything below is either operational (span found, "
            "validator pass, citation fidelity, cost, latency) or **agreement between methods**, which "
            "measures consistency, not correctness."
        )
        L.append("")
    if gold_note:
        L.append(f"> {gold_note}")
        L.append("")

    L.append("## Methods")
    L.append("")
    L.append("| method | extractor version | backend | model | prompt | docs | errors |")
    L.append("|---|---|---|---|---|---:|---:|")
    for m in methods:
        s = summaries[m]
        L.append(
            f"| {m} | `{s['extractor_version']}` | {s['backend'] or '—'} | {s['model_id'] or '—'} | "
            f"{s['prompt_sha'] or '—'} | {s['n_docs']} | {s['n_errors']} |"
        )
    L.append("")

    L.append("## Headline table")
    L.append("")
    L.append("| metric | " + " | ".join(methods) + " |")
    L.append("|---|" + "---:|" * len(methods))
    for name, fn in HEADLINE:
        L.append(f"| {name} | " + " | ".join(fn(summaries[m]) for m in methods) + " |")
    L.append("")

    if agreements:
        L.append("## Agreement between methods (span IoU, all docs)")
        L.append("")
        L.append("| pair | n | IoU mean | IoU median | IoU ≥ 0.9 |")
        L.append("|---|---:|---:|---:|---:|")
        for ag in agreements:
            L.append(
                f"| {ag['a']} ↔ {ag['b']} | {ag['n']} | {_num(ag['iou_mean'])} | "
                f"{_num(ag['iou_median'])} | {_pct(ag['iou_ge_0.9'])} |"
            )
        L.append("")

    src = strata.get("source", {})
    if src:
        L.append("## By source (audit set vs rules failures)")
        L.append("")
        L.append(
            "| source | " + " | ".join(f"{m}: span found / validator pass / IoU vs gold (n)" for m in methods) + " |"
        )
        L.append("|---|" + "---|" * len(methods))
        groups = sorted({g for m in methods for g in src.get(m, {})})
        for g in groups:
            cells = []
            for m in methods:
                st = src.get(m, {}).get(g)
                if st is None:
                    cells.append("—")
                else:
                    cells.append(
                        f"{_pct(st['span_found_rate'])} / {_pct(st['validation_pass_rate'])} / "
                        f"{_num(st['iou_mean'])} (n={st['n_docs']})"
                    )
            L.append(f"| {g} | " + " | ".join(cells) + " |")
        L.append("")

    L.append("## Field coverage (LLM-only fields; the rules path emits none)")
    L.append("")
    L.append("| field | " + " | ".join(methods) + " |")
    L.append("|---|" + "---:|" * len(methods))
    for name, key, is_pct in FIELDS:
        fmt = _pct if is_pct else _num
        L.append(f"| {name} | " + " | ".join(fmt(summaries[m]["fields"][key]) for m in methods) + " |")
    L.append("")

    for c in comparisons:
        if c["n_pairs"]:
            L.append(f"## {c['b']} vs {c['a']} on labeled docs (paired IoU)")
            L.append("")
            L.append(
                f"- pairs {c['n_pairs']} · mean IoU delta {_num(c['iou_delta_mean'])} · "
                f"wins {c['wins']} / ties {c['ties']} / losses {c['losses']}"
            )
            L.append("")

    ds_path = run_dir / "downstream.json"
    if ds_path.exists():
        ds = json.loads(ds_path.read_text(encoding="utf-8"))
        L.extend(_downstream_section(ds))

    L.append("## Validator flags and extractor notes")
    L.append("")
    for m in methods:
        L.append(f"- **{m}** flags: `{summaries[m]['flags'] or {}}`")
        L.append(f"- **{m}** notes (top): `{summaries[m]['notes'] or {}}`")
    L.append("")

    L.append("## How to read this")
    L.append("")
    L.append(
        "- *IoU vs gold* compares each method's span with the gold span, on labeled documents only. Gold labels "
        "are either human (Noah) or judge-accepted (Opus 5 verdicts accepted under an explicit policy, "
        "`labeler=judge:…`); `legallm-xeval --labeler human` restricts to the human labels."
    )
    L.append(
        "- *Agreement* is IoU between the two methods' spans on every document; high agreement with low "
        "gold IoU means both are wrong the same way."
    )
    L.append(
        "- *Citation fidelity* is the share of emitted case/record citations that occur verbatim in the "
        "source (whitespace- and dash-insensitive). *Citation support* also accepts cites the source prints "
        "as list/range shorthand (`App.1494, 1503` → `App.1503`) when every number occurs near the same "
        "prefix; a wrong pincite or an expanded range stays unsupported. The rules path emits only "
        "regex-found cites, so both are 1.0 by construction."
    )
    L.append(
        "- *Recovered span* is the share of `no_facts_span` failure documents with a human-located facts "
        "section where the method's span reaches IoU ≥ 0.5."
    )
    L.append(
        "- Cost for `claude-cli` runs is the CLI's estimate at API list prices; those runs are billed to "
        "the subscription, not per token."
    )
    L.append("")
    L.append(
        f"Full report: `{run_dir.as_posix()}/report.md`. Regenerate: `legallm-xeval --render {run_dir.as_posix()}`."
    )
    L.append("")
    return "\n".join(L)
