"""C13 regression gate: run the smoke eval offline and fail if a method regressed against the committed baseline.

    legallm-gate                      # compare against evals/ci/smoke_baseline.json (exit 1 on regression)
    legallm-gate --update-baseline    # after an intended change: rewrite the baseline from the current run

The smoke set is ``tests/fixtures/xeval_smoke`` (3 synthetic briefs, labeled) and the LLM responses for it are
frozen under ``tests/fixtures/xeval_smoke/cache`` (recorded once with ``claude-cli``), so the gate needs no
credentials and exercises the whole code path after the model: anchor location, validators, routing, IoU vs gold.
Thresholds (D8): span IoU may not drop by more than 2 points, citation fidelity/support by more than 1 point;
span-found may not drop; no extractor errors. The same command runs on the weekly schedule as the drift check.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SMOKE_GOLD = Path("tests/fixtures/xeval_smoke/gold_smoke.jsonl")
SMOKE_CACHE = Path("tests/fixtures/xeval_smoke/cache")
DEFAULT_BASELINE = Path("evals/ci/smoke_baseline.json")
DEFAULT_METHODS = ["rules_v2", "llm-v2", "llm-v3"]

# metric -> maximum allowed drop (current must be >= baseline - drop)
DEFAULT_THRESHOLDS: dict[str, float] = {
    "iou_mean": 0.02,
    "citation_fidelity_mean": 0.01,
    "citation_support_mean": 0.01,
    "span_found_rate": 0.0,
}


@dataclass
class Check:
    method: str
    metric: str
    baseline: float | None
    current: float | None
    max_drop: float
    ok: bool
    note: str = ""

    @property
    def delta(self) -> float | None:
        if self.baseline is None or self.current is None:
            return None
        return self.current - self.baseline


def run_smoke(
    methods: list[str],
    *,
    gold: Path = SMOKE_GOLD,
    cache_dir: Path = SMOKE_CACHE,
    backend: str = "claude-cli",
    runs_dir: Path | None = None,
    offline: bool = True,
) -> dict[str, Any]:
    """Run the smoke eval (offline by default) and return ``summary.json``'s content."""
    from legallm.extraction_eval import run_eval
    from legallm.llm_extractor import configure_default

    configure_default(backend=backend)
    rd = runs_dir or Path(tempfile.mkdtemp(prefix="legallm_gate_"))
    out = run_eval(
        gold_path=gold,
        methods=methods,
        subset="all",
        runs_dir=rd,
        cache_dir=cache_dir,
        offline=offline,
        run_label="gate",
    )
    data: dict[str, Any] = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    data["meta"]["run_dir"] = out.as_posix()
    return data


def compare(
    current: dict[str, Any], baseline: dict[str, Any] | None, thresholds: dict[str, float] | None = None
) -> list[Check]:
    th = thresholds or DEFAULT_THRESHOLDS
    checks: list[Check] = []
    base_methods = (baseline or {}).get("methods", {})
    for m, s in current["summaries"].items():
        n_err = int(s.get("n_errors") or 0)
        checks.append(Check(m, "n_errors", 0.0, float(n_err), 0.0, n_err == 0, "extractor errors" if n_err else ""))
        b = base_methods.get(m)
        for metric, drop in th.items():
            cur = s.get(metric)
            bv = None if b is None else b.get(metric)
            if bv is None or cur is None:
                checks.append(Check(m, metric, bv, cur, drop, True, "no baseline" if bv is None else "n/a"))
                continue
            ok = float(cur) >= float(bv) - drop - 1e-9
            checks.append(Check(m, metric, float(bv), float(cur), drop, ok, "" if ok else "REGRESSION"))
    return checks


def baseline_from(current: dict[str, Any], thresholds: dict[str, float]) -> dict[str, Any]:
    return {
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "gold": Path(str(current["meta"].get("gold_path"))).as_posix(),
        "n_docs": current["meta"].get("n_docs"),
        "thresholds": dict(thresholds),
        "methods": {
            m: {k: s.get(k) for k in [*thresholds, "n_errors", "validation_pass_rate"]}
            for m, s in current["summaries"].items()
        },
    }


def _f(x: float | None) -> str:
    return "—" if x is None else f"{x:.3f}"


def format_gate(
    checks: list[Check], *, passed: bool, run_dir: str | None = None, baseline_path: Path | None = None
) -> str:
    L = [f"## Smoke regression gate: {'PASS' if passed else 'FAIL'}", ""]
    if baseline_path is not None:
        L.append(f"Baseline `{baseline_path.as_posix()}` · run `{run_dir}`")
        L.append("")
    L.append("| method | metric | baseline | current | Δ | max drop | status |")
    L.append("|---|---|---:|---:|---:|---:|---|")
    for c in checks:
        d = c.delta
        status = "ok" if c.ok else "**FAIL**"
        if c.note and c.ok:
            status = c.note
        L.append(
            f"| {c.method} | {c.metric} | {_f(c.baseline)} | {_f(c.current)} | "
            f"{'—' if d is None else f'{d:+.3f}'} | {c.max_drop:.2f} | {status} |"
        )
    L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="legallm-gate", description="Offline smoke eval + regression gate (CI).")
    ap.add_argument("--methods", nargs="+", default=DEFAULT_METHODS)
    ap.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    ap.add_argument("--update-baseline", action="store_true", help="rewrite the baseline from this run and exit 0")
    ap.add_argument("--gold", type=Path, default=SMOKE_GOLD)
    ap.add_argument("--cache-dir", type=Path, default=SMOKE_CACHE)
    ap.add_argument("--backend", default="claude-cli", help="backend the cached responses were recorded with")
    ap.add_argument("--online", action="store_true", help="allow live extractor calls for uncached docs")
    ap.add_argument("--iou-drop", type=float, default=DEFAULT_THRESHOLDS["iou_mean"])
    ap.add_argument("--fidelity-drop", type=float, default=DEFAULT_THRESHOLDS["citation_fidelity_mean"])
    ap.add_argument("--runs-dir", type=Path, default=None)
    ap.add_argument("--summary-out", type=Path, default=None, help="write the markdown table here as well")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(errors="replace")  # type: ignore[union-attr]
    except Exception:  # pragma: no cover
        pass
    thresholds = {
        **DEFAULT_THRESHOLDS,
        "iou_mean": args.iou_drop,
        "citation_fidelity_mean": args.fidelity_drop,
        "citation_support_mean": args.fidelity_drop,
    }
    current = run_smoke(
        args.methods,
        gold=args.gold,
        cache_dir=args.cache_dir,
        backend=args.backend,
        runs_dir=args.runs_dir,
        offline=not args.online,
    )
    if args.update_baseline:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(baseline_from(current, thresholds), indent=2), encoding="utf-8")
        print(f"baseline written: {args.baseline}")
        checks = compare(current, None, thresholds)
        passed = all(c.ok for c in checks)
    else:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline.exists() else None
        if baseline is None:
            print(f"no baseline at {args.baseline}; run with --update-baseline first", file=sys.stderr)
        checks = compare(current, baseline, thresholds)
        passed = all(c.ok for c in checks) and baseline is not None
    md = format_gate(checks, passed=passed, run_dir=current["meta"].get("run_dir"), baseline_path=args.baseline)
    print(md)
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(md, encoding="utf-8")
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write(md + "\n")
    return 0 if passed else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
