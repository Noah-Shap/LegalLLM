"""Headless test for the side-by-side UI (C11) via streamlit.testing.v1.AppTest — in-process rules_v2 only."""

import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "src" / "legallm" / "ui_app.py"


def test_paste_text_rules_only(tmp_path, monkeypatch, sample_brief_text):
    log = tmp_path / "requests.jsonl"
    monkeypatch.setenv("LEGALLM_REQUEST_LOG", str(log))
    monkeypatch.setenv("LEGALLM_DEFAULT_METHOD", "rules_v2")
    monkeypatch.delenv("LEGALLM_API_URL", raising=False)
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    at.text_area(key="pasted").set_value(sample_brief_text).run()
    at.button(key="run").click().run()
    assert not at.exception, at.exception
    text = "\n".join(str(m.value) for m in at.markdown) + "\n".join(str(m.value) for m in at.metric)
    assert "chars" in text
    metrics = {m.label: m.value for m in at.metric}
    assert metrics.get("validator") == "OK" and metrics.get("span", "none") != "none"
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1 and rows[0]["method"] == "rules_v2" and rows[0]["span_found"] is True


def test_empty_input_shows_error(tmp_path, monkeypatch):
    monkeypatch.setenv("LEGALLM_REQUEST_LOG", str(tmp_path / "r.jsonl"))
    monkeypatch.setenv("LEGALLM_DEFAULT_METHOD", "rules_v2")
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.button(key="run").click().run()
    assert any("upload a file or paste text" in str(e.value) for e in at.error)
