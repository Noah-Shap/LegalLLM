"""Tests for legallm.api (C10 service). Offline: rules_v2 and a fake llm method; no network, no model calls."""

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from legallm.api import RateLimiter, Settings, create_app, llm_available  # noqa: E402
from legallm.schema import FactsExtraction  # noqa: E402
from legallm.single_doc import EXTRACTORS, register_extractor  # noqa: E402


def _fake_llm(doc_text: str, doc_type_id: str) -> FactsExtraction:
    from legallm.baseline_adapter import extract_rules

    ex = extract_rules(doc_text, doc_type_id)
    return FactsExtraction(
        **{
            **ex.model_dump(),
            "extractor_version": "llm-fake",
            "parties": ["Appellant", "Appellee"],
            "procedural_posture": "Appeal.",
            "provenance": {
                "backend": "fake",
                "model_id": "claude-fake",
                "prompt_sha": "p",
                "cost_usd": 0.02,
                "latency_s": 1.5,
                "input_tokens": 10,
                "output_tokens": 5,
                "tier": "cheap",
                "routing": {"trigger": None, "escalated": False},
            },
        }
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    register_extractor("llm-fake", _fake_llm)
    monkeypatch.setattr("legallm.api.llm_available", lambda backend: (True, "fake"))
    settings = Settings(
        default_method="llm-fake", llm_backend="api", request_log=tmp_path / "requests.jsonl", rate_limit_per_min=0
    )
    app = create_app(settings)
    yield TestClient(app), tmp_path / "requests.jsonl"
    EXTRACTORS.pop("llm-fake", None)


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


class TestHealth:
    def test_health(self, client):
        c, _ = client
        r = c.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok" and "rules_v2" in body["methods"] and body["default_method"] == "llm-fake"
        assert body["llm_available"] is True
        assert c.get("/methods").json()["baseline"] == "rules_v2"

    def test_llm_available_api_backend(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        assert llm_available("api")[0] is False
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        assert llm_available("api")[0] is True


class TestExtract:
    def test_text_json_rules(self, client, sample_brief_text):
        c, log = client
        r = c.post("/extract", json={"text": sample_brief_text, "method": "rules_v2"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["method"] == "rules_v2" and body["baseline"] is None
        assert body["result"]["extraction"]["facts_span"] is not None
        assert body["result"]["validation"]["ok"] is True
        assert body["doc"]["kind"] == "text" and body["doc"]["chars"] > 0 and len(body["doc"]["sha1"]) == 16
        rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 1 and rows[0]["method"] == "rules_v2" and rows[0]["span_found"] is True
        assert "doc_text" not in rows[0] and "text" not in rows[0]

    def test_default_method_with_baseline_compare(self, client, sample_brief_text):
        c, log = client
        r = c.post("/extract", json={"text": sample_brief_text})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["method"] == "llm-fake" and body["baseline"]["method"] == "rules_v2"
        assert body["result"]["extraction"]["parties"] == ["Appellant", "Appellee"]
        row = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
        assert row["model_id"] == "claude-fake" and row["cost_usd"] == 0.02 and row["compare"] is True
        assert row["baseline"]["method"] == "rules_v2" and row["tier"] == "cheap"

    def test_baseline_offsets_refer_to_the_same_text(self, client, sample_brief_text):
        c, _ = client
        # a leading form feed + PACER-style header make normalize/preprocess non-trivial
        text = "\x0cCase: 24-1234  Document: 12  Page: 1\n" + sample_brief_text
        body = c.post("/extract", json={"text": text}).json()
        direct = c.post("/extract", json={"text": text, "method": "rules_v2"}).json()
        base_span = body["baseline"]["extraction"]["facts_span"]
        direct_span = direct["result"]["extraction"]["facts_span"]
        assert (base_span["start"], base_span["end"]) == (direct_span["start"], direct_span["end"])
        assert body["doc"]["sha1"] == direct["doc"]["sha1"]

    def test_compare_false(self, client, sample_brief_text):
        c, _ = client
        body = c.post("/extract", json={"text": sample_brief_text, "compare": False}).json()
        assert body["baseline"] is None

    def test_upload_txt_and_pdf(self, client, sample_brief_text, tmp_path):
        c, log = client
        r = c.post(
            "/extract",
            files={"file": ("brief.txt", sample_brief_text.encode("utf-8"))},
            data={"method": "rules_v2", "compare": "false"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["doc"]["kind"] == "text" and r.json()["doc"]["source"] == "brief.txt"
        pdf = tmp_path / "brief.pdf"
        _make_pdf(pdf, sample_brief_text)
        r = c.post(
            "/extract", files={"file": ("brief.pdf", pdf.read_bytes(), "application/pdf")}, data={"method": "rules_v2"}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert (
            body["doc"]["kind"] == "pdf"
            and body["doc"]["pages"] == 1
            and body["doc"]["text_extractor"] in ("pypdf", "pymupdf")
        )
        assert body["result"]["extraction"]["facts_span"] is not None
        rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        assert rows[-1]["source_kind"] == "pdf" and rows[-1]["pages"] == 1

    def test_errors(self, client, sample_brief_text):
        c, log = client
        assert c.post("/extract", json={"text": sample_brief_text, "method": "nope"}).status_code == 400
        assert c.post("/extract", json={"text": "   "}).status_code == 422
        assert c.post("/extract", json={"method": "rules_v2"}).status_code == 422
        assert c.post("/extract", data={"method": "rules_v2"}, files={"other": ("x.txt", b"x")}).status_code == 422
        rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        assert all(r["error"] for r in rows) and rows[0]["error"].startswith("400")

    def test_llm_unavailable_503(self, tmp_path, monkeypatch, sample_brief_text):
        register_extractor("llm-fake", _fake_llm)
        try:
            monkeypatch.setattr("legallm.api.llm_available", lambda backend: (False, "no creds"))
            c = TestClient(
                create_app(Settings(default_method="llm-fake", request_log=tmp_path / "r.jsonl", rate_limit_per_min=0))
            )
            r = c.post("/extract", json={"text": sample_brief_text})
            assert r.status_code == 503 and "no creds" in r.json()["detail"]
            assert c.post("/extract", json={"text": sample_brief_text, "method": "rules_v2"}).status_code == 200
        finally:
            EXTRACTORS.pop("llm-fake", None)

    def test_upload_too_large(self, tmp_path, monkeypatch, sample_brief_text):
        c = TestClient(
            create_app(
                Settings(default_method="rules_v2", request_log=None, max_upload_mb=0.00001, rate_limit_per_min=0)
            )
        )
        r = c.post("/extract", files={"file": ("brief.txt", sample_brief_text.encode("utf-8"))})
        assert r.status_code == 413

    def test_rate_limit(self, tmp_path, sample_brief_text):
        c = TestClient(create_app(Settings(default_method="rules_v2", request_log=None, rate_limit_per_min=2)))
        codes = [c.post("/extract", json={"text": sample_brief_text}).status_code for _ in range(3)]
        assert codes == [200, 200, 429]


class TestRateLimiter:
    def test_window(self):
        rl = RateLimiter(2)
        assert rl.allow("a", now=0.0) and rl.allow("a", now=1.0) and not rl.allow("a", now=2.0)
        assert rl.allow("b", now=2.0)
        assert rl.allow("a", now=61.5)  # first hit expired
        assert RateLimiter(0).allow("a")


def test_module_app_importable():
    from legallm import api

    assert api.app.title.startswith("Legal facts")
    assert Path(api.DEFAULT_LOG).name == "requests.jsonl"
