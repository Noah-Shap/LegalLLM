"""C13 regression gate: run the smoke eval offline and fail if a method regressed against the committed baseline.

    legallm-gate                      # compare against evals/ci/smoke_baseline.json (exit 1 on regression)
    legallm-gate --update-baseline    # after an intended change: rewrite the baseline from the current run

The smoke set is ``tests/fixtures/xeval_smoke`` (3 synthetic briefs, labeled). The raw model responses for it are
recorded once (``legallm-gate --record --backend claude-cli``) into ``tests/fixtures/xeval_smoke/responses.jsonl``,
keyed by model + prompt + document, and replayed through the real extractor on every run — so the gate needs no
credentials yet exercises everything after the model: anchor location, schema parsing, validators, routing, IoU vs
gold. (A cache of finished extractions would not: a regression in ``locate_span`` passed such a gate unnoticed.)
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
SMOKE_RESPONSES = Path("tests/fixtures/xeval_smoke/responses.jsonl")
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


def build_extractors(store: dict[str, Any], *, record: bool = False, backend: str = "claude-cli") -> dict[str, Any]:
    """llm-v2 (cheap) and llm-v3 (routed) extractors; model calls are replayed from, or recorded into, ``store``."""
    from legallm.llm_extractor import LlmConfig, LlmExtractor
    from legallm.replay import RecordingClient, ReplayClient
    from legallm.routing import STRONG_MODEL, RouteConfig, Router

    cheap_cfg = LlmConfig(prompt_version="v2", backend=backend)
    strong_cfg = LlmConfig(prompt_version="v2", backend=backend, model=STRONG_MODEL, effort="high")
    if record:
        client: Any = RecordingClient(LlmExtractor(cheap_cfg).client, store)
    else:
        client = ReplayClient(store)
    cheap = LlmExtractor(cheap_cfg, client=client)
    strong = LlmExtractor(strong_cfg, client=client)
    router = Router(RouteConfig(backend=backend), cheap=cheap, strong=strong)
    return {"llm-v2": cheap, "llm-v3": router}


def run_smoke(
    methods: list[str],
    *,
    gold: Path = SMOKE_GOLD,
    responses: Path = SMOKE_RESPONSES,
    backend: str = "claude-cli",
    runs_dir: Path | None = None,
    record: bool = False,
) -> dict[str, Any]:
    """Run the smoke eval through the real extractors with replayed (or, with ``record``, live+recorded) model calls."""
    from legallm.extraction_eval import run_eval
    from legallm.replay import load_responses, save_responses

    store = load_responses(responses)
    extractors = build_extractors(store, record=record, backend=backend)
    rd = runs_dir or Path(tempfile.mkdtemp(prefix="legallm_gate_"))
    out = run_eval(
        gold_path=gold,
        methods=methods,
        subset="all",
        runs_dir=rd,
        cache_dir=None,
        extractors={m: fn for m, fn in extractors.items() if m in methods},
        run_label="gate",
    )
    if record:
        save_responses(responses, store)
    data: dict[str, Any] = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    data["meta"]["run_dir"] = out.as_posix()
    data["meta"]["responses"] = Path(responses).as_posix()
    data["meta"]["n_recordings"] = len(store)
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
    ap.add_argument("--responses", type=Path, default=SMOKE_RESPONSES, help="recorded model responses (JSONL)")
    ap.add_argument("--backend", default="claude-cli", help="backend used when recording (--record)")
    ap.add_argument("--record", action="store_true", help="call the models live and (re)write --responses")
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
        responses=args.responses,
        backend=args.backend,
        runs_dir=args.runs_dir,
        record=args.record,
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
