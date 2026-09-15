"""Tests for legallm.results_page (item 7 results renderer)."""

from pathlib import Path

from legallm.extraction_eval import main, run_eval
from legallm.results_page import render_results
from legallm.schema import FactsExtraction

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "xeval_smoke"
GOLD = FIXTURES / "gold_smoke.jsonl"


def _fake_llm(doc_text: str, doc_type_id: str) -> FactsExtraction:
    from legallm.baseline_adapter import extract_rules

    ex = extract_rules(doc_text, doc_type_id)
    return FactsExtraction(
        **{
            **ex.model_dump(),
            "extractor_version": "llm-fake",
            "parties": ["A", "B"],
            "procedural_posture": "Appeal.",
            "provenance": {"backend": "fake", "model_id": "m", "prompt_sha": "p", "cost_usd": 0.02, "latency_s": 1.5},
        }
    )


def test_render_from_run_dir(tmp_path):
    out = run_eval(
        gold_path=GOLD,
        methods=["rules_v2", "llm-fake"],
        subset="all",
        runs_dir=tmp_path / "runs",
        cache_dir=None,
        extractors={"llm-fake": _fake_llm},
    )
    page = render_results(out)
    assert page.startswith("# Results — facts extraction")
    assert "Labels pending" not in page  # fixture gold is fully labeled
    iou_line = next(line for line in page.splitlines() if line.startswith("| IoU vs gold (mean) |"))
    assert "—" not in iou_line  # labeled fixture: both methods get a number (s002's gold is trimmed, so < 1.0)
    assert "rules_v2 ↔ llm-fake" in page
    assert "| parties non-empty | 0.0% | 100.0% |" in page
    assert "| cost / doc | — | $0.020 |" in page
    assert "## How to read this" in page


def test_labels_pending_banner(tmp_path):
    # unlabeled gold: strip statuses
    from legallm.gold import load_gold, save_gold

    recs = load_gold(GOLD)
    for r in recs:
        r.status = "pending"
    gold = tmp_path / "gold.jsonl"
    save_gold(recs, gold)
    out = run_eval(gold_path=gold, methods=["rules_v2"], subset="all", runs_dir=tmp_path / "runs", cache_dir=None)
    page = render_results(out, gold_note="custom note")
    assert "Labels pending" in page and "custom note" in page
    assert "| IoU vs gold (mean) | — |" in page


def test_cli_render(tmp_path, capsys):
    out = run_eval(gold_path=GOLD, methods=["rules_v2"], subset="all", runs_dir=tmp_path / "runs", cache_dir=None)
    target = tmp_path / "RESULTS.md"
    assert main(["--render", str(out), "--results-out", str(target)]) == 0
    assert target.exists() and "wrote" in capsys.readouterr().out
