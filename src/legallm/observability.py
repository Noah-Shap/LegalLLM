"""C12 observability: summarize the service request log and the eval runs into ``evals/dashboard.md``.

    legallm-dashboard [--log logs/requests.jsonl] [--runs evals/runs] [--out evals/dashboard.md]

Request log → volume, error rate, span-found and validator-pass rates, cost (sum / per doc), latency
(p50 / p95), routing escalation rate — per method and per day. Eval runs → quality over time (IoU vs gold per
method per run). The scheduled drift check is the CI smoke eval (C13); this page is what it feeds.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def load_request_log(path: Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    k = max(0, min(len(ys) - 1, round(q * (len(ys) - 1))))
    return ys[k]


def _group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in rows if not r.get("error")]
    lat = [float(r["latency_s"]) for r in rows if r.get("latency_s") is not None]
    costs = [float(r["cost_usd"]) for r in ok if r.get("cost_usd") is not None]
    esc = [r for r in ok if r.get("escalated") is not None]
    return {
        "n": len(rows),
        "n_errors": len(rows) - len(ok),
        "error_rate": (len(rows) - len(ok)) / len(rows) if rows else None,
        "span_found_rate": sum(bool(r.get("span_found")) for r in ok) / len(ok) if ok else None,
        "validation_pass_rate": sum(bool(r.get("validation_ok")) for r in ok) / len(ok) if ok else None,
        "cost_usd_total": round(sum(costs), 4) if costs else 0.0,
        "cost_usd_per_doc": round(statistics.fmean(costs), 4) if costs else None,
        "latency_p50": _pct(lat, 0.5),
        "latency_p95": _pct(lat, 0.95),
        "escalation_rate": sum(bool(r.get("escalated")) for r in esc) / len(esc) if esc else None,
        "top_flags": _top([f.split(":", 1)[0] for r in ok for f in (r.get("flags") or [])]),
        "top_errors": _top([str(r.get("error"))[:60] for r in rows if r.get("error")]),
    }


def _top(items: list[str], n: int = 5) -> dict[str, int]:
    c: dict[str, int] = defaultdict(int)
    for it in items:
        c[it] += 1
    return dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:n])


def summarize_requests(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_method[str(r.get("method"))].append(r)
        by_day[str(r.get("ts", ""))[:10]].append(r)
    return {
        "all": _group(rows),
        "by_method": {m: _group(v) for m, v in sorted(by_method.items())},
        "by_day": {d: _group(v) for d, v in sorted(by_day.items())},
        "first_ts": min((str(r["ts"]) for r in rows if r.get("ts")), default=None),
        "last_ts": max((str(r["ts"]) for r in rows if r.get("ts")), default=None),
    }


def run_history(runs_dir: Path) -> list[dict[str, Any]]:
    """One row per eval run: timestamp, run id, gold n, IoU / cost / latency per method."""
    out: list[dict[str, Any]] = []
    for sp in sorted(Path(runs_dir).glob("*/summary.json")):
        try:
            d = json.loads(sp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        meta = d.get("meta", {})
        out.append(
            {
                "run_id": meta.get("run_id", sp.parent.name),
                "timestamp": str(meta.get("timestamp", ""))[:19],
                "subset": meta.get("subset"),
                "n_docs": meta.get("n_docs"),
                "n_gold": meta.get("n_gold"),
                "methods": {
                    m: {
                        "iou_mean": s.get("iou_mean"),
                        "iou_ge_0.9": s.get("iou_ge_0.9"),
                        "citation_support_mean": s.get("citation_support_mean"),
                        "cost_usd_per_doc": s.get("cost_usd_per_doc"),
                        "latency_s_mean": s.get("latency_s_mean"),
                    }
                    for m, s in d.get("summaries", {}).items()
                },
            }
        )
    out.sort(key=lambda r: r["timestamp"])
    return out


def _f(x: Any, nd: int = 3) -> str:
    return "—" if x is None else f"{x:.{nd}f}"


def _p(x: Any) -> str:
    return "—" if x is None else f"{x:.1%}"


def format_dashboard(req: dict[str, Any], history: list[dict[str, Any]], *, log_path: Path, runs_dir: Path) -> str:
    L: list[str] = []
    L.append("# Dashboard — facts extraction service")
    L.append("")
    L.append(
        f"Generated {datetime.now(UTC).isoformat(timespec='seconds')} · request log `{log_path.as_posix()}` · "
        f"eval runs `{runs_dir.as_posix()}`"
    )
    L.append("")
    a = req["all"]
    L.append("## Requests")
    L.append("")
    if a["n"] == 0:
        L.append("_No requests logged yet._")
    else:
        L.append(
            f"{a['n']} requests from {req['first_ts']} to {req['last_ts']} · "
            f"errors {a['n_errors']} ({_p(a['error_rate'])})."
        )
        L.append("")
        L.append(
            "| method | n | errors | span found | validator pass | cost total | cost / doc | latency p50 | p95 | "
            "escalated | top flags |"
        )
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
        for m, g in req["by_method"].items():
            L.append(
                f"| {m} | {g['n']} | {g['n_errors']} | {_p(g['span_found_rate'])} | {_p(g['validation_pass_rate'])} | "
                f"${g['cost_usd_total']:.2f} | {_f(g['cost_usd_per_doc'])} | {_f(g['latency_p50'], 2)} s | "
                f"{_f(g['latency_p95'], 2)} s | {_p(g['escalation_rate'])} | {g['top_flags'] or '—'} |"
            )
        L.append("")
        L.append("| day | n | errors | cost total | latency p50 |")
        L.append("|---|---:|---:|---:|---:|")
        for d, g in req["by_day"].items():
            L.append(f"| {d} | {g['n']} | {g['n_errors']} | ${g['cost_usd_total']:.2f} | {_f(g['latency_p50'], 2)} s |")
        if a["top_errors"]:
            L.append("")
            L.append("Top errors: " + " · ".join(f"`{k}` ×{v}" for k, v in a["top_errors"].items()))
    L.append("")
    L.append("## Quality over time (eval runs, IoU vs gold)")
    L.append("")
    if not history:
        L.append("_No eval runs found._")
    else:
        methods = sorted({m for h in history for m in h["methods"]})
        L.append(
            "| run | when | subset | docs (gold) | " + " | ".join(f"{m}: IoU / ≥0.9 / $/doc" for m in methods) + " |"
        )
        L.append("|---|---|---|---:|" + "---|" * len(methods))
        for h in history:
            cells = []
            for m in methods:
                s = h["methods"].get(m)
                cells.append(
                    "—" if s is None else f"{_f(s['iou_mean'])} / {_p(s['iou_ge_0.9'])} / {_f(s['cost_usd_per_doc'])}"
                )
            L.append(
                f"| `{h['run_id']}` | {h['timestamp']} | {h['subset']} | {h['n_docs']} ({h['n_gold']}) | "
                + " | ".join(cells)
                + " |"
            )
    L.append("")
    L.append("## How to read this")
    L.append("")
    L.append(
        "- Requests come from the service log (`legallm-api`, `legallm-ui` in-process mode); "
        "no document text is logged."
    )
    L.append(
        "- Cost is the model's token cost at API list prices; `claude-cli` runs are subscription-billed "
        "and report the CLI's estimate."
    )
    L.append(
        "- The drift check is the CI smoke eval (`legallm-xeval --subset smoke`); "
        "a regression there fails the build (C13)."
    )
    L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="legallm-dashboard", description="Render evals/dashboard.md from the request log + eval runs."
    )
    ap.add_argument("--log", type=Path, default=Path("logs/requests.jsonl"))
    ap.add_argument("--runs", type=Path, default=Path("evals/runs"))
    ap.add_argument("--out", type=Path, default=Path("evals/dashboard.md"))
    args = ap.parse_args(argv)
    rows = load_request_log(args.log)
    page = format_dashboard(summarize_requests(rows), run_history(args.runs), log_path=args.log, runs_dir=args.runs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    print(f"wrote {args.out} ({len(rows)} requests)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
