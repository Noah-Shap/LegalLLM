"""Tests for legallm.observability (C12 dashboard)."""

import json
from pathlib import Path

from legallm.observability import format_dashboard, load_request_log, main, run_history, summarize_requests


def _row(ts, method, **kw):
    return {"source_kind": "text", "doc_chars": 1000, "compare": False, "ts": ts, "method": method, **kw}


def _rows():
    return [
        _row(
            "2026-09-16T10:00:00+00:00",
            "llm-v3",
            latency_s=30.0,
            cost_usd=0.3,
            escalated=False,
            span_found=True,
            validation_ok=True,
            flags=[],
        ),
        _row(
            "2026-09-16T10:05:00+00:00",
            "llm-v3",
            latency_s=90.0,
            cost_usd=1.2,
            escalated=True,
            span_found=True,
            validation_ok=False,
            flags=["unsupported_citation:x"],
        ),
        _row(
            "2026-09-17T09:00:00+00:00",
            "rules_v2",
            latency_s=0.01,
            cost_usd=None,
            span_found=False,
            validation_ok=True,
            flags=[],
        ),
        _row("2026-09-17T09:01:00+00:00", "rules_v2", latency_s=0.02, error="400: unknown method"),
    ]


def test_load_and_summarize(tmp_path):
    p = tmp_path / "requests.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in _rows()) + "not json\n", encoding="utf-8")
    rows = load_request_log(p)
    assert len(rows) == 4 and load_request_log(tmp_path / "missing.jsonl") == []
    s = summarize_requests(rows)
    assert s["all"]["n"] == 4 and s["all"]["n_errors"] == 1 and s["all"]["error_rate"] == 0.25
    v3 = s["by_method"]["llm-v3"]
    assert (
        v3["n"] == 2 and v3["escalation_rate"] == 0.5 and v3["cost_usd_total"] == 1.5 and v3["cost_usd_per_doc"] == 0.75
    )
    assert v3["validation_pass_rate"] == 0.5 and v3["top_flags"] == {"unsupported_citation": 1}
    assert v3["latency_p50"] in (30.0, 90.0) and v3["latency_p95"] == 90.0
    r2 = s["by_method"]["rules_v2"]
    assert r2["n"] == 2 and r2["n_errors"] == 1 and r2["cost_usd_per_doc"] is None and r2["span_found_rate"] == 0.0
    assert set(s["by_day"]) == {"2026-09-16", "2026-09-17"}
    assert s["first_ts"].startswith("2026-09-16") and s["last_ts"].startswith("2026-09-17")


def test_run_history_and_dashboard(tmp_path):
    runs = tmp_path / "runs"
    for rid, ts, iou in (("b_1", "2026-09-15T01:00:00", 0.5), ("a_2", "2026-09-16T01:00:00", 0.9)):
        d = runs / rid
        d.mkdir(parents=True)
        (d / "summary.json").write_text(
            json.dumps(
                {
                    "meta": {"run_id": rid, "timestamp": ts, "subset": "labeled", "n_docs": 3, "n_gold": 3},
                    "summaries": {
                        "rules_v2": {
                            "iou_mean": iou,
                            "iou_ge_0.9": 0.5,
                            "cost_usd_per_doc": None,
                            "latency_s_mean": 0.01,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
    (runs / "broken").mkdir()
    (runs / "broken" / "summary.json").write_text("{", encoding="utf-8")
    h = run_history(runs)
    assert [x["run_id"] for x in h] == ["b_1", "a_2"]  # sorted by timestamp, broken skipped
    page = format_dashboard(summarize_requests(_rows()), h, log_path=Path("logs/requests.jsonl"), runs_dir=runs)
    assert page.startswith("# Dashboard") and "| llm-v3 | 2 | 0 |" in page and "`a_2`" in page
    empty = format_dashboard(summarize_requests([]), [], log_path=Path("x"), runs_dir=Path("y"))
    assert "_No requests logged yet._" in empty and "_No eval runs found._" in empty


def test_cli(tmp_path, capsys):
    log = tmp_path / "requests.jsonl"
    log.write_text(json.dumps(_rows()[0]) + "\n", encoding="utf-8")
    out = tmp_path / "dashboard.md"
    assert main(["--log", str(log), "--runs", str(tmp_path / "none"), "--out", str(out)]) == 0
    assert out.exists() and "1 requests" in capsys.readouterr().out
