"""Extraction eval harness (intent.md §5, C7) + deterministic metrics (C6).

    legallm-xeval --methods rules_v2 llm-v1 --subset labeled          # gold-referenced metrics
    legallm-xeval --methods rules_v2 llm-v1 --subset all              # + rules<->llm agreement on unlabeled docs
    legallm-xeval --gold tests/fixtures/xeval_smoke/gold_smoke.jsonl --methods rules_v2 --subset smoke  # CI

Per document and method it records the predicted span, span IoU against the
gold reference, an IoU-derived 3-class auto-rating, validator outcome and
citation fidelity, field coverage, extractor notes, cost and latency — never
the brief text. Outputs go to ``evals/runs/<run_id>/`` (per_doc.jsonl,
summary.json, report.md, manifest.json). LLM responses are cached under
``data/processed/xeval_cache/`` keyed by (method config, doc_sha1) so re-runs
and report tweaks are free.

Reference policy: a document contributes to gold-referenced metrics only when
its gold record is ``labeled`` (gold span, or has_facts=false). Unlabeled
documents contribute to the *agreement* block (IoU between methods) only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legallm.build_manifest import create_manifest, finalize_manifest, write_manifest
from legallm.gold import GoldRecord, document_text, load_gold
from legallm.schema import FactsExtraction
from legallm.validators import validate_extraction

DEFAULT_RUNS_DIR = Path("evals/runs")
DEFAULT_CACHE_DIR = Path("data/processed/xeval_cache")
IOU_CORRECT = 0.9
IOU_PARTIAL = 0.5

# ---------------------------------------------------------------------------
# Metrics primitives
# ---------------------------------------------------------------------------


def span_iou(a: list[int] | None, b: list[int] | None) -> float:
    """Character-level IoU of two [start, end) spans. Both None -> 1.0 (agree: no facts); one None -> 0.0."""
    if a is None and b is None:
        return 1.0
    if a is None or b is None:
        return 0.0
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0


def auto_rating(iou: float | None) -> str | None:
    """Map span IoU onto the 3-class rubric (calibrated against human ratings in the report)."""
    if iou is None:
        return None
    if iou >= IOU_CORRECT:
        return "correct"
    if iou >= IOU_PARTIAL:
        return "partially_correct"
    return "incorrect"


def gold_reference(rec: GoldRecord) -> tuple[list[int] | None, bool]:
    """(reference span, is_gold). is_gold=False means the reference is the unlabeled rules span (agreement only)."""
    if rec.status == "labeled":
        return rec.effective_span, True
    return rec.rules_span, False


# ---------------------------------------------------------------------------
# Per-document result
# ---------------------------------------------------------------------------


@dataclass
class DocEval:
    gold_id: str
    search_result_id: int
    source: str
    stratum: dict[str, str]
    method: str
    extractor_version: str | None = None
    backend: str | None = None
    model_id: str | None = None
    prompt_sha: str | None = None
    gold_status: str = "pending"
    is_gold: bool = False
    human_rating: str | None = None
    gold_has_facts: bool | None = None
    reference_span: list[int] | None = None
    pred_span: list[int] | None = None
    iou: float | None = None
    auto_rating: str | None = None
    span_found: bool = False
    pred_confidence: str | None = None
    validation_ok: bool | None = None
    flags: list[str] = field(default_factory=list)
    citation_fidelity: float | None = None
    n_citations: int = 0
    n_parties: int = 0
    n_key_events: int = 0
    n_record_cites: int = 0
    n_case_cites: int = 0
    has_posture: bool = False
    extractor_notes: list[str] = field(default_factory=list)
    cost_usd: float | None = None
    latency_s: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_doc(
    rec: GoldRecord,
    method: str,
    ex: FactsExtraction | None,
    doc_text: str,
    *,
    error: str | None = None,
    latency_s: float | None = None,
    cached: bool = False,
) -> DocEval:
    ref, is_gold = gold_reference(rec)
    d = DocEval(
        gold_id=rec.gold_id,
        search_result_id=rec.search_result_id,
        source=rec.source,
        stratum=dict(rec.stratum),
        method=method,
        gold_status=rec.status,
        is_gold=is_gold,
        human_rating=rec.label.rating,
        gold_has_facts=rec.label.has_facts,
        reference_span=ref,
        latency_s=latency_s,
        cached=cached,
        error=error,
    )
    if ex is None:
        d.iou = 0.0 if ref is not None else None
        d.auto_rating = auto_rating(d.iou)
        return d
    span = [ex.facts_span.start, ex.facts_span.end] if ex.facts_span is not None else None
    report = validate_extraction(ex, doc_text)
    prov = ex.provenance or {}
    d.extractor_version = ex.extractor_version
    d.backend = prov.get("backend", "local" if not prov else None)
    d.model_id = prov.get("model_id")
    d.prompt_sha = prov.get("prompt_sha")
    d.pred_span = span
    d.iou = span_iou(ref, span)
    d.auto_rating = auto_rating(d.iou)
    d.span_found = span is not None
    d.pred_confidence = ex.confidence
    d.validation_ok = report.ok
    d.flags = list(report.flags)
    d.citation_fidelity = report.citation_fidelity
    d.n_citations = report.n_citations
    d.n_parties = len(ex.parties)
    d.n_key_events = len(ex.key_events)
    d.n_record_cites = len(ex.record_citations)
    d.n_case_cites = len(ex.case_citations)
    d.has_posture = bool(ex.procedural_posture)
    d.extractor_notes = list(ex.notes)
    d.cost_usd = prov.get("cost_usd")
    if d.latency_s is None:
        d.latency_s = prov.get("latency_s")
    d.input_tokens = prov.get("input_tokens")
    d.output_tokens = prov.get("output_tokens")
    return d


# ---------------------------------------------------------------------------
# Extraction cache
# ---------------------------------------------------------------------------


def method_config_sha(method: str) -> str:
    """Stable hash of everything that changes a method's output (prompt, model, effort, backend)."""
    payload = method
    if method.startswith("llm-"):
        from legallm.llm_extractor import get_extractor, method_version

        try:
            ex = get_extractor(method_version(method))
        except KeyError:  # a custom extractor registered under an llm-* name (tests, experiments)
            ex = None
        if ex is not None:
            cfg = ex.config
            payload = f"{method}|{ex.prompt_sha}|{cfg.model}|{cfg.effort}|{cfg.backend}|{cfg.max_doc_chars}"
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


class ExtractionCache:
    """JSONL-per-method cache of FactsExtraction dumps keyed by (config sha, doc_sha1)."""

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR):
        self.dir = Path(cache_dir)
        self._mem: dict[str, dict[str, Any]] = {}

    def _path(self, method: str) -> Path:
        return self.dir / f"{method}.jsonl"

    def _load(self, method: str) -> dict[str, Any]:
        if method not in self._mem:
            entries: dict[str, Any] = {}
            p = self._path(method)
            if p.exists():
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            e = json.loads(line)
                            entries[e["key"]] = e
            self._mem[method] = entries
        return self._mem[method]

    @staticmethod
    def key(config_sha: str, doc_sha1: str) -> str:
        return f"{config_sha}:{doc_sha1}"

    def get(self, method: str, key: str) -> dict[str, Any] | None:
        return self._load(method).get(key)

    def put(self, method: str, key: str, extraction: FactsExtraction, latency_s: float) -> None:
        entry = {
            "key": key,
            "cached_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "latency_s": latency_s,
            "extraction": extraction.model_dump(),
        }
        self._load(method)[key] = entry
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self._path(method), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Running methods over the gold set
# ---------------------------------------------------------------------------


def load_doc_texts(records: list[GoldRecord], *, progress: bool = False) -> dict[str, str]:
    texts: dict[str, str] = {}
    for i, rec in enumerate(records, start=1):
        if progress:
            print(f"  text [{i}/{len(records)}] {rec.gold_id}", file=sys.stderr, end="\r")
        texts[rec.gold_id] = document_text(rec.pdf_path)
    if progress:
        print(file=sys.stderr)
    return texts


def run_method(
    records: list[GoldRecord],
    method: str,
    doc_texts: dict[str, str],
    *,
    cache: ExtractionCache | None = None,
    extractor: Any = None,
    config_sha: str | None = None,
    offline: bool = False,
    force: bool = False,
    progress: bool = False,
) -> list[DocEval]:
    """Run one extractor over the records (cache-aware) and evaluate each document."""
    from legallm.gold import doc_sha1
    from legallm.single_doc import EXTRACTORS

    fn = extractor or EXTRACTORS[method]
    cfg_sha = config_sha or method_config_sha(method)
    out: list[DocEval] = []
    for i, rec in enumerate(records, start=1):
        if progress:
            print(f"  {method} [{i}/{len(records)}] {rec.gold_id}", file=sys.stderr, end="\r")
        text = doc_texts[rec.gold_id]
        key = ExtractionCache.key(cfg_sha, doc_sha1(text))
        entry = None if (cache is None or force) else cache.get(method, key)
        if entry is not None:
            ex = FactsExtraction.model_validate(entry["extraction"])
            out.append(evaluate_doc(rec, method, ex, text, latency_s=entry.get("latency_s"), cached=True))
            continue
        if offline:
            out.append(evaluate_doc(rec, method, None, text, error="offline: not in cache"))
            continue
        t0 = time.perf_counter()
        try:
            ex = fn(text, rec.doc_type_id)
        except Exception as e:  # extractor failure is a measured outcome, not a crash
            out.append(
                evaluate_doc(
                    rec, method, None, text, error=f"{type(e).__name__}: {e}", latency_s=time.perf_counter() - t0
                )
            )
            continue
        latency = time.perf_counter() - t0
        if cache is not None:
            cache.put(method, key, ex, latency)
        out.append(evaluate_doc(rec, method, ex, text, latency_s=latency))
    if progress:
        print(file=sys.stderr)
    return out


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------


def _mean(xs: list[float]) -> float | None:
    return round(statistics.fmean(xs), 4) if xs else None


def _median(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 4) if xs else None


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def summarize(evals: list[DocEval]) -> dict[str, Any]:
    """Aggregate one method's DocEvals. Gold-referenced numbers use only is_gold docs."""
    gold = [d for d in evals if d.is_gold]
    gold_ious = [d.iou for d in gold if d.iou is not None]
    with_cites = [d for d in evals if d.citation_fidelity is not None]
    failures = [d for d in gold if d.source == "no_facts_span"]
    fail_with_facts = [d for d in failures if d.gold_has_facts and d.reference_span is not None]
    fail_no_facts = [d for d in failures if d.gold_has_facts is False]
    rated = [d for d in gold if d.human_rating and d.auto_rating]
    confusion: Counter[tuple[str, str]] = Counter((d.human_rating or "", d.auto_rating or "") for d in rated)
    costs = [d.cost_usd for d in evals if d.cost_usd is not None]
    lats = [d.latency_s for d in evals if d.latency_s is not None]
    flags: Counter[str] = Counter(f.split(":")[0] for d in evals for f in d.flags)
    notes: Counter[str] = Counter(n for d in evals for n in d.extractor_notes if len(n) <= 40)
    return {
        "method": evals[0].method if evals else None,
        "extractor_version": next((d.extractor_version for d in evals if d.extractor_version), None),
        "backend": next((d.backend for d in evals if d.backend), None),
        "model_id": next((d.model_id for d in evals if d.model_id), None),
        "prompt_sha": next((d.prompt_sha for d in evals if d.prompt_sha), None),
        "n_docs": len(evals),
        "n_gold": len(gold),
        "n_errors": sum(d.error is not None for d in evals),
        "iou_mean": _mean(gold_ious),
        "iou_median": _median(gold_ious),
        "iou_ge_0.9": _rate(sum(x >= IOU_CORRECT for x in gold_ious), len(gold_ious)),
        "iou_ge_0.5": _rate(sum(x >= IOU_PARTIAL for x in gold_ious), len(gold_ious)),
        "span_found_rate": _rate(sum(d.span_found for d in evals), len(evals)),
        "validation_pass_rate": _rate(sum(bool(d.validation_ok) for d in evals), len(evals)),
        "empty_facts_rate": _rate(sum("empty_facts" in d.flags for d in evals), len(evals)),
        "citation_fidelity_mean": _mean([d.citation_fidelity for d in with_cites if d.citation_fidelity is not None]),
        "docs_with_unsupported_cites": sum(any(f.startswith("unsupported_citation") for f in d.flags) for d in evals),
        "n_docs_with_cites": len(with_cites),
        "recovered_span_rate": _rate(sum((d.iou or 0) >= IOU_PARTIAL for d in fail_with_facts), len(fail_with_facts)),
        "failure_stratum_n": len(failures),
        "failure_correct_no_facts_rate": _rate(sum(not d.span_found for d in fail_no_facts), len(fail_no_facts)),
        "auto_vs_human_n": len(rated),
        "auto_vs_human_agreement": _rate(sum(d.human_rating == d.auto_rating for d in rated), len(rated)),
        "auto_vs_human_confusion": {f"{h}->{a}": n for (h, a), n in sorted(confusion.items())},
        "fields": {
            "parties_nonempty_rate": _rate(sum(d.n_parties > 0 for d in evals), len(evals)),
            "posture_rate": _rate(sum(d.has_posture for d in evals), len(evals)),
            "key_events_mean": _mean([float(d.n_key_events) for d in evals]),
            "record_cites_mean": _mean([float(d.n_record_cites) for d in evals]),
            "case_cites_mean": _mean([float(d.n_case_cites) for d in evals]),
        },
        "cost_usd_per_doc": _mean(costs),
        "cost_usd_total": round(sum(costs), 4) if costs else None,
        "latency_s_mean": _mean(lats),
        "latency_s_median": _median(lats),
        "flags": dict(flags.most_common()),
        "notes": dict(notes.most_common(15)),
    }


def stratify(evals: list[DocEval], key: str) -> dict[str, dict[str, Any]]:
    """Summaries grouped by a stratum key ('confidence', 'len_bin') or by 'source'."""
    groups: dict[str, list[DocEval]] = {}
    for d in evals:
        g = d.source if key == "source" else d.stratum.get(key, "unknown")
        groups.setdefault(g, []).append(d)
    return {g: summarize(v) for g, v in sorted(groups.items())}


def agreement(a: list[DocEval], b: list[DocEval]) -> dict[str, Any]:
    """Pairwise span IoU between two methods over all docs (labeled or not)."""
    bm = {d.gold_id: d for d in b}
    ious = [span_iou(d.pred_span, bm[d.gold_id].pred_span) for d in a if d.gold_id in bm]
    return {
        "n": len(ious),
        "iou_mean": _mean(ious),
        "iou_median": _median(ious),
        "iou_ge_0.9": _rate(sum(x >= IOU_CORRECT for x in ious), len(ious)),
    }


def compare(a: list[DocEval], b: list[DocEval], *, worst_n: int = 10) -> dict[str, Any]:
    """Paired gold-referenced IoU deltas (b minus a) plus the worst docs for b."""
    am = {d.gold_id: d for d in a if d.is_gold and d.iou is not None}
    pairs = [
        (am[d.gold_id].iou or 0.0, d.iou or 0.0, d.gold_id)
        for d in b
        if d.is_gold and d.iou is not None and d.gold_id in am
    ]
    deltas = [y - x for x, y, _ in pairs]
    worst = sorted(
        ((d.iou or 0.0), d.gold_id, d.source, d.pred_confidence, ";".join(d.extractor_notes)[:80])
        for d in b
        if d.is_gold and d.iou is not None
    )[:worst_n]
    return {
        "a": a[0].method if a else None,
        "b": b[0].method if b else None,
        "n_pairs": len(pairs),
        "iou_delta_mean": _mean(deltas),
        "wins": sum(dl > 0.01 for dl in deltas),
        "ties": sum(abs(dl) <= 0.01 for dl in deltas),
        "losses": sum(dl < -0.01 for dl in deltas),
        "worst_b": [
            {"iou": round(i, 3), "gold_id": g, "source": s, "confidence": c, "notes": n} for i, g, s, c, n in worst
        ],
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _fmt(x: Any, pct: bool = False) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.1%}" if pct else f"{x:.3f}"
    return str(x)


def _money(x: float | None) -> str:
    return "—" if x is None else f"${x:.4f}"


def _metrics_row(m: str, s: dict[str, Any]) -> str:
    cells = [
        m,
        str(s["n_gold"]),
        _fmt(s["iou_mean"]),
        _fmt(s["iou_median"]),
        _fmt(s["iou_ge_0.9"], True),
        _fmt(s["iou_ge_0.5"], True),
        _fmt(s["span_found_rate"], True),
        _fmt(s["validation_pass_rate"], True),
        _fmt(s["empty_facts_rate"], True),
        _fmt(s["citation_fidelity_mean"]),
        f"{s['docs_with_unsupported_cites']}/{s['n_docs_with_cites']}",
        f"{_fmt(s['recovered_span_rate'], True)} (n={s['failure_stratum_n']})",
        f"{_fmt(s['auto_vs_human_agreement'], True)} (n={s['auto_vs_human_n']})",
        _money(s["cost_usd_per_doc"]),
        f"{_fmt(s['latency_s_mean'])}s",
    ]
    return "| " + " | ".join(cells) + " |"


def _stratum_cell(s: dict[str, Any] | None) -> str:
    if s is None:
        return "—"
    return (
        f"n={s['n_docs']}/{s['n_gold']} · {_fmt(s['iou_mean'])} · "
        f"{_fmt(s['span_found_rate'], True)} · {_fmt(s['validation_pass_rate'], True)}"
    )


def format_report(
    meta: dict[str, Any],
    summaries: dict[str, dict[str, Any]],
    strata: dict[str, dict[str, dict[str, dict[str, Any]]]],
    agreements: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> str:
    L: list[str] = []
    L.append(f"# Extraction eval — run {meta['run_id']}")
    L.append("")
    L.append(
        f"- gold: `{meta['gold_path']}` · subset **{meta['subset']}** · docs {meta['n_docs']} "
        f"(gold-labeled {meta['n_gold']}) · {meta['timestamp']}"
    )
    for m, summ in summaries.items():
        L.append(
            f"- **{m}**: version `{summ['extractor_version']}` · backend `{summ['backend']}` · "
            f"model `{summ['model_id']}` · prompt `{summ['prompt_sha']}`"
        )
    L.append("")
    L.append("## Gold-referenced metrics (labeled docs only)")
    L.append("")
    header = [
        "method",
        "n gold",
        "IoU mean",
        "IoU median",
        "IoU≥0.9",
        "IoU≥0.5",
        "span found",
        "validator pass",
        "empty facts",
        "cite fidelity",
        "docs w/ unsupported cites",
        "recovered (failure stratum)",
        "auto↔human agree",
        "cost/doc",
        "latency/doc",
    ]
    L.append("| " + " | ".join(header) + " |")
    L.append("|---|" + "---:|" * (len(header) - 1))
    for m, summ in summaries.items():
        L.append(_metrics_row(m, summ))
    L.append("")
    L.append(
        "Auto-rating thresholds: IoU ≥ 0.9 → correct, ≥ 0.5 → partially_correct, else incorrect. "
        "Span-found / validator / fidelity / cost / latency columns use **all** docs in the subset."
    )
    L.append("")
    for m, summ in summaries.items():
        if summ["auto_vs_human_confusion"]:
            L.append(f"### {m}: auto-rating vs human rating (human→auto)")
            L.append("")
            L.append("| pair | n |")
            L.append("|---|---:|")
            for pair, n in summ["auto_vs_human_confusion"].items():
                L.append(f"| {pair} | {n} |")
            L.append("")
    if agreements:
        L.append("## Agreement between methods (all docs, no gold needed)")
        L.append("")
        L.append("| pair | n | IoU mean | IoU median | IoU≥0.9 |")
        L.append("|---|---:|---:|---:|---:|")
        for ag in agreements:
            L.append(
                f"| {ag['a']} ↔ {ag['b']} | {ag['n']} | {_fmt(ag['iou_mean'])} | "
                f"{_fmt(ag['iou_median'])} | {_fmt(ag['iou_ge_0.9'], True)} |"
            )
        L.append("")
    for key, per_method in strata.items():
        L.append(f"## Stratified by {key} (n docs/gold · gold-referenced IoU mean · span found · validator pass)")
        L.append("")
        groups = sorted({grp for pm in per_method.values() for grp in pm})
        L.append("| " + key + " | " + " | ".join(per_method.keys()) + " |")
        L.append("|---|" + "---|" * len(per_method))
        for grp in groups:
            cells = [_stratum_cell(per_method[m].get(grp)) for m in per_method]
            L.append(f"| {grp} | " + " | ".join(cells) + " |")
        L.append("")
    for c in comparisons:
        L.append(f"## {c['b']} vs {c['a']} (paired, gold-referenced)")
        L.append("")
        L.append(
            f"- pairs: {c['n_pairs']} · IoU delta mean: {_fmt(c['iou_delta_mean'])} · "
            f"wins {c['wins']} / ties {c['ties']} / losses {c['losses']} (±0.01)"
        )
        if c["worst_b"]:
            L.append("")
            L.append(f"Worst {len(c['worst_b'])} docs for {c['b']}:")
            L.append("")
            L.append("| IoU | gold_id | source | confidence | notes |")
            L.append("|---:|---|---|---|---|")
            for w in c["worst_b"]:
                L.append(
                    f"| {w['iou']:.3f} | {w['gold_id']} | {w['source']} | {w['confidence'] or '—'} | {w['notes']} |"
                )
        L.append("")
    L.append("## Validator flags and extractor notes (all docs)")
    L.append("")
    for m, summ in summaries.items():
        L.append(f"- **{m}** flags: {summ['flags'] or '{}'}")
        L.append(f"- **{m}** notes: {summ['notes'] or '{}'}")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Orchestration + CLI
# ---------------------------------------------------------------------------


def select_records(records: list[GoldRecord], subset: str, limit: int | None) -> list[GoldRecord]:
    if subset == "labeled":
        sel = [r for r in records if r.status == "labeled"]
    elif subset == "all":
        sel = list(records)
    elif subset == "smoke":
        labeled = [r for r in records if r.status == "labeled"]
        sel = (labeled or list(records))[: (limit or 10)]
    else:
        raise ValueError(f"unknown subset {subset!r}")
    if limit:
        sel = sel[:limit]
    return sel


def run_eval(
    *,
    gold_path: Path,
    methods: list[str],
    subset: str = "labeled",
    limit: int | None = None,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    cache_dir: Path | None = DEFAULT_CACHE_DIR,
    offline: bool = False,
    force: bool = False,
    progress: bool = False,
    extractors: dict[str, Any] | None = None,
    run_label: str | None = None,
) -> Path:
    """Run every method over the selected gold docs; write per_doc.jsonl, summary.json, report.md, manifest.json."""
    records = select_records(load_gold(gold_path), subset, limit)
    if not records:
        raise ValueError(f"no records selected (gold={gold_path}, subset={subset})")
    doc_texts = load_doc_texts(records, progress=progress)
    cache = ExtractionCache(cache_dir) if cache_dir is not None else None
    params = {
        "gold_path": str(gold_path),
        "methods": methods,
        "subset": subset,
        "limit": limit,
        "n_docs": len(records),
        "offline": offline,
    }
    manifest = create_manifest(params)
    run_id = (
        (run_label + "_" if run_label else "")
        + datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        + "_"
        + manifest.build_id[:6]
    )
    out_dir = Path(runs_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    per_method: dict[str, list[DocEval]] = {}
    for m in methods:
        per_method[m] = run_method(
            records,
            m,
            doc_texts,
            cache=cache,
            extractor=(extractors or {}).get(m),
            offline=offline,
            force=force,
            progress=progress,
        )
    with open(out_dir / "per_doc.jsonl", "w", encoding="utf-8") as f:
        for m in methods:
            for d in per_method[m]:
                f.write(json.dumps(d.to_dict()) + "\n")

    summaries = {m: summarize(v) for m, v in per_method.items()}
    strata = {key: {m: stratify(v, key) for m, v in per_method.items()} for key in ("source", "confidence", "len_bin")}
    agreements = [
        dict(agreement(per_method[a], per_method[b]), a=a, b=b) for i, a in enumerate(methods) for b in methods[i + 1 :]
    ]
    comparisons = [compare(per_method[methods[0]], per_method[m]) for m in methods[1:]]
    meta = {
        "run_id": run_id,
        "gold_path": str(gold_path),
        "subset": subset,
        "n_docs": len(records),
        "n_gold": sum(r.status == "labeled" for r in records),
        "timestamp": manifest.timestamp_utc,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(
            {
                "meta": meta,
                "summaries": summaries,
                "strata": strata,
                "agreements": agreements,
                "comparisons": comparisons,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "report.md").write_text(
        format_report(meta, summaries, strata, agreements, comparisons), encoding="utf-8"
    )
    finalize_manifest(
        manifest,
        {
            "run_id": run_id,
            "methods": {
                m: {
                    k: s[k]
                    for k in (
                        "extractor_version",
                        "backend",
                        "model_id",
                        "prompt_sha",
                        "n_docs",
                        "n_gold",
                        "iou_mean",
                        "cost_usd_total",
                    )
                }
                for m, s in summaries.items()
            },
        },
    )
    write_manifest(manifest, out_dir / "manifest.json")
    return out_dir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="legallm-xeval", description="Extraction eval harness: methods x gold docs -> metrics report."
    )
    ap.add_argument("--gold", type=Path, default=Path("evals/gold/gold_v1.jsonl"))
    ap.add_argument(
        "--methods", nargs="+", default=["rules_v2"], help="registered extractor names (rules_v2, llm-v1, ...)"
    )
    ap.add_argument("--subset", choices=["labeled", "all", "smoke"], default="labeled")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    ap.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--offline", action="store_true", help="never call an extractor that is not cached (CI)")
    ap.add_argument("--force", action="store_true", help="ignore cached extractions")
    ap.add_argument("--backend", choices=["api", "claude-cli"], default=None, help="LLM transport for llm-* methods")
    ap.add_argument("--label", default=None, help="prefix for the run id (e.g. 'llm-v1-first')")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument(
        "--render", type=Path, default=None, help="render the results page from an existing run dir and exit"
    )
    ap.add_argument("--results-out", type=Path, default=Path("evals/RESULTS.md"), help="where --render writes")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252; the report uses ≥ / ↔ / —
        sys.stdout.reconfigure(errors="replace")
    if args.render is not None:
        from legallm.results_page import render_results

        page = render_results(args.render)
        args.results_out.parent.mkdir(parents=True, exist_ok=True)
        args.results_out.write_text(page, encoding="utf-8")
        print(page)
        print(f"wrote {args.results_out}")
        return 0
    if args.backend:
        from legallm.llm_extractor import configure_default

        configure_default(backend=args.backend)
    try:
        out = run_eval(
            gold_path=args.gold,
            methods=args.methods,
            subset=args.subset,
            limit=args.limit,
            runs_dir=args.runs_dir,
            cache_dir=None if args.no_cache else args.cache_dir,
            offline=args.offline,
            force=args.force,
            progress=not args.quiet,
            run_label=args.label,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print((out / "report.md").read_text(encoding="utf-8"))
    print(f"run dir: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
