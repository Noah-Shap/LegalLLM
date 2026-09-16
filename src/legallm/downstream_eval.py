"""Downstream evaluation (C6): does a better facts span help what sits after extraction?

Two downstream consumers already exist in the pipeline and are re-run here on each
method's span (rules_v2, llm-vN) and on the gold span, over the gold documents:

1. **Citation resolution** — case citations found in the span (``citation_extractor``)
   are looked up in the CourtListener resolver cache (``citation_resolver.CitationCache``).
   Per R5 nothing is fetched: a citation missing from the cache is counted as *uncached*,
   never queried. Reported as the share of documents with ≥ 1 resolved citation (the
   pipeline's 58.5 % figure), cite-level counts, and the method's resolved-target set
   against the gold span's (precision / recall).
2. **BM25 Recall@10** — the retrieval baseline (``baselines.BM25Baseline``) is fitted on the
   canonical 2k build's train split *minus the gold documents* (so a gold query can never
   retrieve itself) and queried with the masked span text. Targets are fixed per document
   (the gold span's resolved citations), so only the query text differs between methods.

    legallm-downstream --run evals/runs/<xeval run> --parquet data/processed/facts_dataset_2k.parquet

Outputs ``<run>/downstream.json`` and ``<run>/downstream.md``; ``results_page`` picks the JSON
up when it exists.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from legallm.baselines import BM25Baseline
from legallm.citation_extractor import deduplicate_case_citations, extract_citations, mask_citations
from legallm.citation_resolver import CitationCache
from legallm.dataset import load_dataset
from legallm.eval_harness import evaluate
from legallm.gold import GoldRecord, load_gold
from legallm.schema import FactsExtraction

GOLD_METHOD = "gold"
DEFAULT_PARQUET = Path("data/processed/facts_dataset_2k.parquet")
DEFAULT_CACHE = Path("data/processed/citation_cache.json")
DEFAULT_GOLD = Path("evals/gold/gold_v1.jsonl")

# ---------------------------------------------------------------------------
# Citation resolution from a span (cache only — R5)
# ---------------------------------------------------------------------------


@dataclass
class CiteStats:
    n_case_cites: int = 0
    n_unique: int = 0
    n_resolved: int = 0
    n_cached_unresolved: int = 0
    n_uncached: int = 0
    targets: list[str] = field(default_factory=list)


def span_cites(text: str, cache: CitationCache) -> CiteStats:
    """Case citations in ``text`` resolved through the cache; never hits the network."""
    st = CiteStats()
    if not text:
        return st
    res = extract_citations(text)
    st.n_case_cites = len(res.case_citations)
    uniq = {c.normalized for c in deduplicate_case_citations(res.case_citations) if c.normalized}
    st.n_unique = len(uniq)
    seen: set[str] = set()
    for norm in sorted(uniq):
        entry = cache.get(norm)
        if entry is None:
            st.n_uncached += 1
        elif entry.resolution_status == "resolved" and entry.resolved_id:
            st.n_resolved += 1
            rid = str(entry.resolved_id)
            if rid not in seen:
                seen.add(rid)
                st.targets.append(rid)
        else:
            st.n_cached_unresolved += 1
    return st


# ---------------------------------------------------------------------------
# Inputs: spans from an xeval run, the modeling split
# ---------------------------------------------------------------------------


def spans_from_run(run_dir: Path, methods: list[str]) -> tuple[dict[str, dict[str, list[int] | None]], dict[str, Any]]:
    """({method: {gold_id: pred_span}}, {gold_id: {"reference_span", "gold_has_facts", "is_gold"}})."""
    spans: dict[str, dict[str, list[int] | None]] = {m: {} for m in methods}
    ref: dict[str, Any] = {}
    with open(Path(run_dir) / "per_doc.jsonl", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r["method"] in spans:
                spans[r["method"]][r["gold_id"]] = r["pred_span"]
            ref.setdefault(
                r["gold_id"],
                {
                    "reference_span": r.get("reference_span"),
                    "gold_has_facts": r.get("gold_has_facts"),
                    "is_gold": bool(r.get("is_gold")),
                },
            )
    return spans, ref


def load_modeling_split(parquet: Path, *, split_cache: Path | None = None, refresh: bool = False) -> pd.DataFrame:
    """The modeling DataFrame (dedup + split) for the canonical build; cached because dedup is slow (~5 min)."""
    cols = ["search_result_id", "row_id", "split", "targets", "facts_text_masked", "label_cardinality_bin"]
    if split_cache is not None and split_cache.exists() and not refresh:
        return pd.read_parquet(split_cache)
    df = load_dataset(parquet)
    out = df[cols].copy()
    out["search_result_id"] = out["search_result_id"].astype(str)
    if split_cache is not None:
        split_cache.parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(split_cache, index=False)
    return out


# ---------------------------------------------------------------------------
# Query builders (plan item 1A): what text stands for the document when retrieving
# ---------------------------------------------------------------------------


def _fields_text(ex: FactsExtraction | None) -> str:
    """Posture + event texts + parties from a structured extraction (empty if none)."""
    if ex is None:
        return ""
    parts: list[str] = []
    if ex.procedural_posture:
        parts.append(ex.procedural_posture)
    parts.extend(ev.text for ev in ex.key_events if ev.text)
    parts.extend(ex.parties)
    return " ".join(parts)


def _events_text(ex: FactsExtraction | None) -> str:
    return " ".join(ev.text for ev in ex.key_events if ev.text) if ex is not None else ""


def build_query(builder: str, span_text: str, ex: FactsExtraction | None) -> str | None:
    """Query text for one builder; ``None`` when the builder needs fields the method does not produce.

    Builders: ``narrative`` (masked span text — the Phase-1 query), ``fields`` / ``fields3`` / ``fields5`` (posture +
    events + parties, repeated 1/3/5 times), ``fields+narrative`` / ``fields3+narrative`` (fields prepended to the
    narrative), ``events`` (event texts only).
    """
    narrative = mask_citations(span_text) if span_text else ""
    if builder == "narrative":
        return narrative
    if ex is None:
        return None
    if builder == "events":
        return _events_text(ex)
    weight = 1
    base = builder
    if "+narrative" in builder:
        base = builder.replace("+narrative", "")
    if base.startswith("fields"):
        weight = int(base[6:] or "1")
        fields = " ".join([_fields_text(ex)] * weight)
        return fields + (" " + narrative if builder.endswith("+narrative") else "")
    raise KeyError(f"unknown query builder {builder!r}; known: {QUERY_BUILDERS}")


QUERY_BUILDERS: tuple[str, ...] = (
    "narrative",
    "fields",
    "fields3",
    "fields5",
    "fields+narrative",
    "fields3+narrative",
    "events",
)


def load_extractions(
    methods: list[str],
    records: dict[str, GoldRecord],
    doc_texts: dict[str, str],
    *,
    cache_dir: Path | None = None,
    backend: str = "claude-cli",
) -> dict[str, dict[str, FactsExtraction]]:
    """Cached extractions per llm method (for their structured fields); rules/gold have none."""
    from legallm.extraction_eval import DEFAULT_CACHE_DIR, ExtractionCache, method_config_sha
    from legallm.gold import doc_sha1
    from legallm.llm_extractor import configure_default

    configure_default(backend=backend)
    cache = ExtractionCache(cache_dir or DEFAULT_CACHE_DIR)
    out: dict[str, dict[str, FactsExtraction]] = {}
    for m in methods:
        if not m.startswith("llm-"):
            continue
        sha = method_config_sha(m)
        found: dict[str, FactsExtraction] = {}
        for g, rec in records.items():
            entry = cache.get(m, ExtractionCache.key(sha, doc_sha1(doc_texts[g])))
            if entry is not None:
                found[g] = FactsExtraction.model_validate(entry["extraction"])
        out[m] = found
    return out


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def _slice(text: str, span: list[int] | None) -> str:
    if not span:
        return ""
    return text[span[0] : span[1]]


def _retrieve(model: BM25Baseline, queries: list[dict[str, Any]], k: int) -> dict[str, tuple[float, float]]:
    """{row_id: (recall@k, mrr@k)} for masked query texts against fixed targets."""
    if not queries:
        return {}
    qdf = pd.DataFrame(queries)
    results = model.predict(qdf, k=max(k, 50))
    metrics = evaluate(results, qdf, ks=[k])
    return {q.row_id: (q.recall[k], q.mrr[k]) for q in metrics.per_query}


def run_downstream(
    run_dir: Path,
    *,
    methods: list[str],
    gold_path: Path = DEFAULT_GOLD,
    parquet: Path = DEFAULT_PARQUET,
    cache_path: Path = DEFAULT_CACHE,
    split_cache: Path | None = None,
    refresh_split: bool = False,
    k: int = 10,
    doc_texts: dict[str, str] | None = None,
    write: bool = True,
    progress: bool = False,
    query_builders: tuple[str, ...] | list[str] | None = None,
    extractions: dict[str, dict[str, FactsExtraction]] | None = None,
    cache_dir: Path | None = None,
    backend: str = "claude-cli",
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    records = [r for r in load_gold(gold_path) if r.status == "labeled"]
    by_id: dict[str, GoldRecord] = {r.gold_id: r for r in records}
    spans, ref = spans_from_run(run_dir, methods)
    gold_ids = [g for g in by_id if g in ref and ref[g]["is_gold"]]
    if doc_texts is None:
        from legallm.extraction_eval import load_doc_texts

        doc_texts = load_doc_texts([by_id[g] for g in gold_ids], progress=progress)
    cache = CitationCache(cache_path)
    all_methods = list(methods) + [GOLD_METHOD]
    for g in gold_ids:
        spans.setdefault(GOLD_METHOD, {})[g] = ref[g]["reference_span"]

    # --- 1. citations per doc × method ------------------------------------------------
    cites: dict[str, dict[str, CiteStats]] = {m: {} for m in all_methods}
    for m in all_methods:
        for g in gold_ids:
            cites[m][g] = span_cites(_slice(doc_texts[g], spans[m].get(g)), cache)
    gold_targets = {g: set(cites[GOLD_METHOD][g].targets) for g in gold_ids}

    # --- 2. retrieval ------------------------------------------------------------------
    df = load_modeling_split(parquet, split_cache=split_cache, refresh=refresh_split)
    sids = {str(by_id[g].search_result_id) for g in gold_ids}
    train_all = df[df["split"] == "train"]
    train = train_all[~train_all["search_result_id"].isin(sids)]
    test = df[df["split"] == "test"]
    bm25 = BM25Baseline(n_retrieve=100)
    bm25.fit(train)
    # baseline reproduction on the canonical build's own test split (rules spans, parquet text)
    base = BM25Baseline(n_retrieve=100)
    base.fit(train_all)
    base_m = evaluate(base.predict(test, k=50), test, ks=[k])
    baseline = {
        "n_test_queries": base_m.n_queries,
        f"recall@{k}": base_m.mean_recall.get(k),
        f"mrr@{k}": base_m.mean_mrr.get(k),
        "n_train": int(len(train_all)),
        "n_train_minus_gold": int(len(train)),
        "n_gold_in_train": int(len(train_all) - len(train)),
    }
    query_ids = [g for g in gold_ids if gold_targets[g]]
    parquet_targets: dict[str, list[str]] = {}
    for g in gold_ids:
        rows = df[df["search_result_id"] == str(by_id[g].search_result_id)]
        if len(rows):
            parquet_targets[g] = list(rows.iloc[0]["targets"])
    alt_ids = [g for g in gold_ids if parquet_targets.get(g)]
    retrieval: dict[str, dict[str, tuple[float, float]]] = {}
    retrieval_alt: dict[str, dict[str, tuple[float, float]]] = {}
    for m in all_methods:
        qs = [
            {
                "row_id": g,
                "facts_text_masked": mask_citations(_slice(doc_texts[g], spans[m].get(g))),
                "targets": sorted(gold_targets[g]),
            }
            for g in query_ids
        ]
        retrieval[m] = _retrieve(bm25, qs, k)
        qs_alt = [
            {
                "row_id": g,
                "facts_text_masked": mask_citations(_slice(doc_texts[g], spans[m].get(g))),
                "targets": parquet_targets[g],
            }
            for g in alt_ids
        ]
        retrieval_alt[m] = _retrieve(bm25, qs_alt, k)

    # --- 3. per-doc rows + summaries ---------------------------------------------------
    per_doc: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, Any]] = {}
    n_docs = len(gold_ids)
    facts_ids = [g for g in gold_ids if ref[g]["gold_has_facts"]]
    nofacts_ids = [g for g in gold_ids if not ref[g]["gold_has_facts"]]
    for m in all_methods:
        tp = fp = fn = 0
        resolved_any = resolved_any_facts = 0
        with_span = 0
        spurious_docs = spurious_targets = 0
        tot = CiteStats()
        for g in gold_ids:
            c = cites[m][g]
            sp = spans[m].get(g)
            if sp:
                with_span += 1
            tgt = set(c.targets)
            tp += len(tgt & gold_targets[g])
            fp += len(tgt - gold_targets[g])
            fn += len(gold_targets[g] - tgt)
            if c.n_resolved:
                resolved_any += 1
                if ref[g]["gold_has_facts"]:
                    resolved_any_facts += 1
            if not ref[g]["gold_has_facts"] and tgt:
                spurious_docs += 1
                spurious_targets += len(tgt)
            tot.n_case_cites += c.n_case_cites
            tot.n_unique += c.n_unique
            tot.n_resolved += c.n_resolved
            tot.n_cached_unresolved += c.n_cached_unresolved
            tot.n_uncached += c.n_uncached
            rec_ = retrieval[m].get(g)
            alt_ = retrieval_alt[m].get(g)
            per_doc.append(
                {
                    "gold_id": g,
                    "method": m,
                    "span": sp,
                    "gold_has_facts": ref[g]["gold_has_facts"],
                    **{k_: v for k_, v in asdict(c).items()},
                    "gold_targets": sorted(gold_targets[g]),
                    f"recall@{k}": None if rec_ is None else rec_[0],
                    f"mrr@{k}": None if rec_ is None else rec_[1],
                    f"recall@{k}_parquet_targets": None if alt_ is None else alt_[0],
                }
            )
        rq = retrieval[m]
        ra = retrieval_alt[m]
        rq_span = [rq[g][0] for g in query_ids if spans[m].get(g)]
        summaries[m] = {
            "method": m,
            "n_docs": n_docs,
            "docs_with_span": with_span,
            "docs_resolved_ge1": resolved_any,
            "docs_resolved_ge1_rate": resolved_any / n_docs if n_docs else None,
            "docs_with_facts": len(facts_ids),
            "docs_resolved_ge1_rate_facts_only": resolved_any_facts / len(facts_ids) if facts_ids else None,
            "n_case_cites": tot.n_case_cites,
            "n_unique_cites": tot.n_unique,
            "n_resolved": tot.n_resolved,
            "n_cached_unresolved": tot.n_cached_unresolved,
            "n_uncached": tot.n_uncached,
            "uncached_share": tot.n_uncached / tot.n_unique if tot.n_unique else None,
            "target_precision": tp / (tp + fp) if (tp + fp) else None,
            "target_recall": tp / (tp + fn) if (tp + fn) else None,
            "spurious_target_docs": spurious_docs,
            "spurious_targets": spurious_targets,
            "n_nofacts_docs": len(nofacts_ids),
            "n_queries": len(query_ids),
            f"recall@{k}": sum(v[0] for v in rq.values()) / len(rq) if rq else None,
            f"mrr@{k}": sum(v[1] for v in rq.values()) / len(rq) if rq else None,
            f"recall@{k}_span_found": sum(rq_span) / len(rq_span) if rq_span else None,
            "n_queries_span_found": len(rq_span),
            "n_queries_parquet_targets": len(alt_ids),
            f"recall@{k}_parquet_targets": sum(v[0] for v in ra.values()) / len(ra) if ra else None,
        }

    # --- 2b. query builders (1A): same index and targets, different query text per llm method ----------
    builders = tuple(query_builders) if query_builders else ()
    qb: dict[str, dict[str, dict[str, Any]]] = {}
    if builders:
        llm_methods = [m for m in methods if m.startswith("llm-")]
        if extractions is None:
            extractions = load_extractions(llm_methods, by_id, doc_texts, cache_dir=cache_dir, backend=backend)
        for m in llm_methods:
            exs = extractions.get(m, {})
            per_builder: dict[str, dict[str, Any]] = {}
            base_scores: dict[str, tuple[float, float]] | None = None
            for b in builders:
                qs = []
                for g in query_ids:
                    q = build_query(b, _slice(doc_texts[g], spans[m].get(g)), exs.get(g))
                    if q is None:
                        q = ""
                    qs.append({"row_id": g, "facts_text_masked": q, "targets": sorted(gold_targets[g])})
                scores = _retrieve(bm25, qs, k)
                if b == "narrative":
                    base_scores = scores
                wins = ties = losses = 0
                if base_scores is not None and b != "narrative":
                    for g in query_ids:
                        a_, b_ = base_scores[g][0], scores[g][0]
                        if b_ > a_ + 1e-9:
                            wins += 1
                        elif a_ > b_ + 1e-9:
                            losses += 1
                        else:
                            ties += 1
                per_builder[b] = {
                    "n": len(query_ids),
                    "n_with_fields": sum(1 for g in query_ids if g in exs),
                    f"recall@{k}": sum(v[0] for v in scores.values()) / len(scores) if scores else None,
                    f"mrr@{k}": sum(v[1] for v in scores.values()) / len(scores) if scores else None,
                    "wins": wins,
                    "ties": ties,
                    "losses": losses,
                }
            qb[m] = per_builder

    # paired vs the first method (rules) on recall@k
    comparisons: list[dict[str, Any]] = []
    a = methods[0]
    for b in all_methods[1:]:
        wins = ties = losses = 0
        for g in query_ids:
            ra_, rb_ = retrieval[a][g][0], retrieval[b][g][0]
            if rb_ > ra_ + 1e-9:
                wins += 1
            elif ra_ > rb_ + 1e-9:
                losses += 1
            else:
                ties += 1
        comparisons.append({"a": a, "b": b, "n": len(query_ids), "wins": wins, "ties": ties, "losses": losses})

    out = {
        "meta": {
            "run_dir": run_dir.as_posix(),
            "gold_path": Path(gold_path).as_posix(),
            "parquet": Path(parquet).as_posix(),
            "cache_path": Path(cache_path).as_posix(),
            "cache_entries": len(cache),
            "k": k,
            "n_docs": n_docs,
            "n_queries": len(query_ids),
            "methods": all_methods,
            "network": "none (cache only, R5)",
        },
        "baseline": baseline,
        "summaries": summaries,
        "comparisons": comparisons,
        "query_builders": qb,
    }
    if write:
        (run_dir / "downstream.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        with open(run_dir / "downstream_per_doc.jsonl", "w", encoding="utf-8") as f:
            for row in per_doc:
                f.write(json.dumps(row) + "\n")
        (run_dir / "downstream.md").write_text(format_downstream(out), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _pct(x: Any) -> str:
    return "—" if x is None else f"{x:.1%}"


def _num(x: Any) -> str:
    return "—" if x is None else f"{x:.3f}"


def format_downstream(d: dict[str, Any]) -> str:
    meta, S, B = d["meta"], d["summaries"], d["baseline"]
    k = meta["k"]
    ms = meta["methods"]
    L: list[str] = []
    L.append("# Downstream: citation resolution and BM25 retrieval on each method's span")
    L.append("")
    L.append(
        f"Spans from `{meta['run_dir']}` · {meta['n_docs']} gold docs · resolver cache `{meta['cache_path']}` "
        f"({meta['cache_entries']} entries, **no network calls**) · BM25 fitted on the canonical build's train "
        f"split minus the gold docs ({B['n_train_minus_gold']} of {B['n_train']} rows; {B['n_gold_in_train']} "
        f"gold docs excluded) · fixed targets = the gold span's resolved citations · {meta['n_queries']} queries "
        f"with ≥ 1 target."
    )
    L.append("")
    L.append(
        f"Baseline reproduction on the build's own test split (rules spans, parquet text, BM25 on the full train "
        f"split): Recall@{k} **{_num(B[f'recall@{k}'])}**, MRR@{k} {_num(B[f'mrr@{k}'])}, n = {B['n_test_queries']}."
    )
    L.append("")
    L.append("## Citation resolution (cache lookups of case citations found in the span)")
    L.append("")
    L.append("| metric | " + " | ".join(ms) + " |")
    L.append("|---|" + "---:|" * len(ms))
    rows = [
        ("docs with a span", lambda s: f"{s['docs_with_span']}/{s['n_docs']}"),
        ("docs with ≥ 1 resolved citation (all gold docs)", lambda s: _pct(s["docs_resolved_ge1_rate"])),
        (
            "docs with ≥ 1 resolved citation (docs that have a facts section)",
            lambda s: _pct(s["docs_resolved_ge1_rate_facts_only"]),
        ),
        (
            "unique case cites / resolved / cached-unresolved / uncached",
            lambda s: f"{s['n_unique_cites']} / {s['n_resolved']} / {s['n_cached_unresolved']} / {s['n_uncached']}",
        ),
        ("resolved-target precision vs gold span", lambda s: _pct(s["target_precision"])),
        ("resolved-target recall vs gold span", lambda s: _pct(s["target_recall"])),
        (
            "spurious targets on no-facts docs (docs / targets)",
            lambda s: f"{s['spurious_target_docs']}/{s['n_nofacts_docs']} / {s['spurious_targets']}",
        ),
    ]
    for name, fn in rows:
        L.append(f"| {name} | " + " | ".join(fn(S[m]) for m in ms) + " |")
    L.append("")
    L.append("## BM25 retrieval (query = masked span text; targets fixed per doc)")
    L.append("")
    L.append("| metric | " + " | ".join(ms) + " |")
    L.append("|---|" + "---:|" * len(ms))
    rows2 = [
        (f"Recall@{k} (n = {S[ms[0]]['n_queries']})", lambda s: _num(s[f"recall@{k}"])),
        (f"MRR@{k}", lambda s: _num(s[f"mrr@{k}"])),
        (
            f"Recall@{k}, queries where the method has a span",
            lambda s: f"{_num(s[f'recall@{k}_span_found'])} (n={s['n_queries_span_found']})",
        ),
        (
            f"Recall@{k} with the build's own (rules-derived) targets (n = {S[ms[0]]['n_queries_parquet_targets']})",
            lambda s: _num(s[f"recall@{k}_parquet_targets"]),
        ),
    ]
    for name, fn in rows2:
        L.append(f"| {name} | " + " | ".join(fn(S[m]) for m in ms) + " |")
    L.append("")
    qb = d.get("query_builders") or {}
    if qb:
        L.append(f"## Query builders (plan 1A): same index and targets, different query text (Recall@{k} / MRR@{k})")
        L.append("")
        builders = list(next(iter(qb.values())).keys())
        L.append("| method | " + " | ".join(builders) + " |")
        L.append("|---|" + "---:|" * len(builders))
        for m, per in qb.items():
            cells = []
            for b in builders:
                r = per[b]
                cell = f"{_num(r[f'recall@{k}'])} / {_num(r[f'mrr@{k}'])}"
                if b != "narrative":
                    cell += f" ({r['wins']}/{r['ties']}/{r['losses']})"
                cells.append(cell)
            L.append(f"| {m} | " + " | ".join(cells) + " |")
        L.append("")
        L.append(
            "Cells: Recall / MRR, then paired wins/ties/losses against that method's own `narrative` query. Fields = "
            "procedural posture + key-event texts + parties from the method's extraction; a number after `fields` is "
            "how many times the fields text is repeated (a crude term weight). The checkpoint in "
            "`docs/plan_next.md` §1A is wins − losses ≥ 8 of 31 for some builder."
        )
        L.append("")
    if d["comparisons"]:
        L.append(
            f"Paired Recall@{k} vs `{d['comparisons'][0]['a']}`: "
            + " · ".join(
                f"`{c['b']}` wins {c['wins']} / ties {c['ties']} / losses {c['losses']}" for c in d["comparisons"]
            )
        )
        L.append("")
    L.append("## How to read this")
    L.append("")
    L.append(
        "- *Resolved* means the normalized citation is in the resolver cache with a CourtListener cluster id; "
        "*uncached* citations were never submitted to the resolver (this run makes no network calls), so the "
        "resolution rates are lower bounds for every method alike."
    )
    L.append(
        "- A rules span that spills into the Argument section resolves *more* citations, not fewer — the "
        "precision/recall rows against the gold span's targets, and the spurious-target row on documents with "
        "no facts section, show whether those extra targets are real facts-section citations."
    )
    L.append(
        "- Recall@k asks whether the masked span text retrieves training briefs that cite the same cases. An "
        "empty span is an empty query (recall 0), so the all-queries row penalises has-facts mistakes and anchor "
        "failures; the span-found row isolates query quality."
    )
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Downstream eval: citation resolution + BM25 Recall@k on method spans")
    ap.add_argument("--run", required=True, help="xeval run directory (uses its per_doc.jsonl spans)")
    ap.add_argument("--methods", nargs="+", default=["rules_v2", "llm-v1", "llm-v2"])
    ap.add_argument("--gold", default=str(DEFAULT_GOLD))
    ap.add_argument("--parquet", default=str(DEFAULT_PARQUET))
    ap.add_argument("--cache", default=str(DEFAULT_CACHE), help="resolver cache JSON (read only)")
    ap.add_argument("--split-cache", default="data/processed/facts_dataset_2k.modeling.parquet")
    ap.add_argument("--refresh-split", action="store_true")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument(
        "--query-builders",
        nargs="*",
        default=None,
        help=f"evaluate alternative query texts for llm methods (default: none; 'all' = {' '.join(QUERY_BUILDERS)})",
    )
    ap.add_argument("--backend", default="claude-cli", help="backend the cached extractions were made with")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(errors="replace")  # type: ignore[union-attr]
    except Exception:  # pragma: no cover - non-console stdout
        pass
    out = run_downstream(
        Path(args.run),
        methods=args.methods,
        gold_path=Path(args.gold),
        parquet=Path(args.parquet),
        cache_path=Path(args.cache),
        split_cache=Path(args.split_cache) if args.split_cache else None,
        refresh_split=args.refresh_split,
        k=args.k,
        progress=not args.quiet,
        query_builders=(QUERY_BUILDERS if args.query_builders == ["all"] else (args.query_builders or None)),
        backend=args.backend,
    )
    if not args.quiet:
        k = args.k
        for m, s in out["summaries"].items():
            print(
                f"{m:>10}: resolved>=1 {s['docs_resolved_ge1_rate']:.1%} | target P/R "
                f"{_pct(s['target_precision'])}/{_pct(s['target_recall'])} | R@{k} {_num(s[f'recall@{k}'])} "
                f"(span-found {_num(s[f'recall@{k}_span_found'])}, n={s['n_queries_span_found']})"
            )
        print(f"wrote {Path(args.run) / 'downstream.md'}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
