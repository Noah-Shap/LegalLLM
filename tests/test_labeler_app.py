"""Headless UI test for the Streamlit labeler (C5) via streamlit.testing.v1.AppTest."""

import json
from pathlib import Path

import pandas as pd
import pytest

from legallm.gold import build_manifest, load_gold, save_gold

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "src" / "legallm" / "labeler_app.py"


def _make_pdf(path, text):
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    page = doc.new_page()
    y = 40
    for line in text.splitlines():
        page.insert_text((40, y), line, fontsize=8)
        y += 11
    doc.save(str(path))
    doc.close()


@pytest.fixture
def gold_file(tmp_path, sample_brief_text, monkeypatch):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    for sid in (11, 12, 21):
        _make_pdf(pdf_dir / f"{sid}.pdf", sample_brief_text)
    from legallm.single_doc import extract_from_file

    sp = extract_from_file(pdf_dir / "11.pdf", method="rules_v2").extraction.facts_span
    pd.DataFrame(
        {
            "search_result_id": [11, 12],
            "pdf_url": ["u1", "u2"],
            "doc_type_id": ["UNKNOWN"] * 2,
            "extractor_confidence": ["high", "low"],
            "len_bin": ["short"] * 2,
            "facts_start": [sp.start] * 2,
            "facts_end": [sp.end] * 2,
            "extractor_notes": ["", ""],
            "extractor_method": ["rules_v2"] * 2,
        }
    ).to_parquet(tmp_path / "audit.parquet", index=False)
    (tmp_path / "failures.jsonl").write_text(
        json.dumps({"reason": "no_facts_span", "search_id": 21, "pdf_url": "u3", "notes": ["no_span_found"]}) + "\n",
        encoding="utf-8",
    )
    recs = build_manifest(tmp_path / "audit.parquet", tmp_path / "failures.jsonl", pdf_dir, n_failures=1)
    gold = tmp_path / "gold_v1.jsonl"
    save_gold(recs, gold)
    monkeypatch.setenv("LEGALLM_GOLD_PATH", str(gold))
    monkeypatch.setenv("LEGALLM_LABELER", "tester")
    return gold


def test_renders_and_saves_a_label(gold_file):
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception, at.exception
    assert at.session_state["cur"] == "g001"
    # rate the rules span and save
    at.radio(key="r_g001").set_value("partially_correct").run()
    at.text_area(key="n_g001").set_value("edge trimmed").run()
    at.button(key="save").click().run()
    assert not at.exception, at.exception

    recs = {r.gold_id: r for r in load_gold(gold_file)}
    g1 = recs["g001"]
    assert g1.status == "labeled"
    assert g1.label.rating == "partially_correct"
    assert g1.label.notes == "edge trimmed"
    assert g1.label.labeler == "tester"
    assert g1.label.gold_span == g1.rules_span  # default: gold span saved from the rules span
    # UI advanced to the next pending document
    assert at.session_state["cur"] == "g002"


def test_failure_record_marked_no_facts(gold_file):
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.session_state["cur"] = "f001"
    at.run()
    assert not at.exception, at.exception
    at.radio(key="hf_f001").set_value("no").run()
    at.button(key="save").click().run()
    assert not at.exception, at.exception
    f1 = {r.gold_id: r for r in load_gold(gold_file)}["f001"]
    assert f1.status == "labeled" and f1.label.has_facts is False and f1.label.gold_span is None


def test_skip_marks_skipped(gold_file):
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.button(key="skip").click().run()
    assert not at.exception, at.exception
    assert {r.gold_id: r.status for r in load_gold(gold_file)}["g001"] == "skipped"
