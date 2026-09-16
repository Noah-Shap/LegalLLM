"""Tests for legallm.ci_gate (C13 regression gate). Offline: rules_v2 on the smoke fixtures."""

import json
from pathlib import Path

import pytest

from legallm.ci_gate import DEFAULT_THRESHOLDS, baseline_from, compare, format_gate, main, run_smoke


def _summary(**per_method):
    return {"meta": {"gold_path": "g", "n_docs": 3}, "summaries": per_method}


class TestCompare:
    def test_regression_detected(self):
        cur = _summary(
            rules_v2={
                "iou_mean": 0.80,
                "citation_fidelity_mean": 1.0,
                "citation_support_mean": 1.0,
                "span_found_rate": 1.0,
                "n_errors": 0,
            }
        )
        base = baseline_from(
            _summary(
                rules_v2={
                    "iou_mean": 0.85,
                    "citation_fidelity_mean": 1.0,
                    "citation_support_mean": 1.0,
                    "span_found_rate": 1.0,
                    "n_errors": 0,
                }
            ),
            DEFAULT_THRESHOLDS,
        )
        checks = compare(cur, base)
        bad = [c for c in checks if not c.ok]
        assert [(c.method, c.metric) for c in bad] == [("rules_v2", "iou_mean")]
        assert bad[0].delta == pytest.approx(-0.05) and bad[0].note == "REGRESSION"

    def test_within_threshold_and_missing_metrics(self):
        cur = _summary(
            m={
                "iou_mean": 0.84,
                "citation_fidelity_mean": None,
                "citation_support_mean": 0.995,
                "span_found_rate": 1.0,
                "n_errors": 0,
            }
        )
        base = baseline_from(
            _summary(
                m={
                    "iou_mean": 0.85,
                    "citation_fidelity_mean": 1.0,
                    "citation_support_mean": 1.0,
                    "span_found_rate": 1.0,
                    "n_errors": 0,
                }
            ),
            DEFAULT_THRESHOLDS,
        )
        checks = compare(cur, base)
        assert all(c.ok for c in checks)
        assert next(c for c in checks if c.metric == "citation_fidelity_mean").note == "n/a"

    def test_errors_and_new_method(self):
        cur = _summary(new={"iou_mean": 0.5, "n_errors": 2})
        checks = compare(cur, None)
        assert next(c for c in checks if c.metric == "n_errors").ok is False
        assert all(c.note == "no baseline" for c in checks if c.metric != "n_errors")
        md = format_gate(checks, passed=False, run_dir="r", baseline_path=Path("b.json"))
        assert md.startswith("## Smoke regression gate: FAIL") and "**FAIL**" in md and "no baseline" in md


class TestRunAndCli:
    def test_run_smoke_rules_only(self, tmp_path):
        data = run_smoke(["rules_v2"], runs_dir=tmp_path / "runs", cache_dir=tmp_path / "cache")
        s = data["summaries"]["rules_v2"]
        assert s["n_errors"] == 0 and s["iou_mean"] is not None and data["meta"]["n_docs"] == 3

    def test_cli_update_then_gate_then_regression(self, tmp_path, capsys, monkeypatch):
        base = tmp_path / "baseline.json"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "step.md"))
        rc = main(
            [
                "--methods",
                "rules_v2",
                "--baseline",
                str(base),
                "--update-baseline",
                "--runs-dir",
                str(tmp_path / "r1"),
                "--cache-dir",
                str(tmp_path / "c"),
            ]
        )
        assert rc == 0 and base.exists()
        b = json.loads(base.read_text(encoding="utf-8"))
        assert "rules_v2" in b["methods"] and b["thresholds"]["iou_mean"] == 0.02
        rc = main(
            [
                "--methods",
                "rules_v2",
                "--baseline",
                str(base),
                "--runs-dir",
                str(tmp_path / "r2"),
                "--cache-dir",
                str(tmp_path / "c"),
                "--summary-out",
                str(tmp_path / "gate.md"),
            ]
        )
        assert rc == 0 and "PASS" in (tmp_path / "gate.md").read_text(encoding="utf-8")
        assert "Smoke regression gate" in (tmp_path / "step.md").read_text(encoding="utf-8")
        # tamper: pretend the baseline IoU was much higher -> regression
        b["methods"]["rules_v2"]["iou_mean"] = 1.5  # impossible baseline -> guaranteed regression
        base.write_text(json.dumps(b), encoding="utf-8")
        rc = main(
            [
                "--methods",
                "rules_v2",
                "--baseline",
                str(base),
                "--runs-dir",
                str(tmp_path / "r3"),
                "--cache-dir",
                str(tmp_path / "c"),
            ]
        )
        assert rc == 1 and "FAIL" in capsys.readouterr().out

    def test_missing_baseline_fails(self, tmp_path, capsys):
        rc = main(
            [
                "--methods",
                "rules_v2",
                "--baseline",
                str(tmp_path / "none.json"),
                "--runs-dir",
                str(tmp_path / "r"),
                "--cache-dir",
                str(tmp_path / "c"),
            ]
        )
        assert rc == 1 and "no baseline" in capsys.readouterr().err
