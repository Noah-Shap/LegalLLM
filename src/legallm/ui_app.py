"""C11 minimal UI (Streamlit): upload a brief (PDF/text) → extraction side-by-side with the rules baseline.

    legallm-ui                      # in-process extraction (same code path as legallm-extract)
    LEGALLM_API_URL=http://host:8000 legallm-ui   # call the FastAPI service instead

Shows, for the chosen method and for rules_v2: span position and preview, confidence, extractor notes, validator
verdict + flags, structured fields (parties, posture, key events, citations), and provenance (model, routing
tier, tokens, cost, latency). Requests made in-process are appended to the same JSONL log as the API.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import streamlit as st

from legallm.api import RequestLogger, llm_available, log_record, run_baseline
from legallm.baseline_adapter import RULES_VERSION
from legallm.single_doc import EXTRACTORS, SingleDocResult, extract_from_file, extract_from_text

API_URL = os.environ.get("LEGALLM_API_URL", "").rstrip("/")
DEFAULT_METHOD = os.environ.get("LEGALLM_DEFAULT_METHOD", "llm-v3")
BACKEND = os.environ.get("LEGALLM_LLM_BACKEND", "api")
LOG_PATH = Path(os.environ.get("LEGALLM_REQUEST_LOG", "logs/requests.jsonl"))
MAX_PER_SESSION = int(os.environ.get("LEGALLM_UI_MAX_PER_SESSION", "20"))


def _result_dict(r: SingleDocResult) -> dict[str, Any]:
    return {
        "method": r.method,
        "extraction": r.extraction.model_dump(),
        "validation": r.validation.to_dict(),
        "elapsed_s": r.elapsed_s,
    }


def run_in_process(
    *, text: str | None, upload: tuple[str, bytes] | None, method: str, doc_type_id: str, compare: bool
) -> dict[str, Any]:
    from legallm.llm_extractor import configure_default

    configure_default(backend=BACKEND)
    t0 = time.perf_counter()
    if upload is not None:
        name, data = upload
        suffix = Path(name).suffix.lower() or ".txt"
        if suffix == ".pdf":
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(data)
                tmp = Path(f.name)
            try:
                result = extract_from_file(tmp, method=method, doc_type_id=doc_type_id, require_facts=False)
            finally:
                tmp.unlink(missing_ok=True)
            result.source = name
        else:
            result = extract_from_text(
                data.decode("utf-8", errors="replace"),
                method=method,
                doc_type_id=doc_type_id,
                source=name,
                require_facts=False,
            )
    else:
        result = extract_from_text(text or "", method=method, doc_type_id=doc_type_id, require_facts=False)
    baseline = None
    if compare and method != RULES_VERSION:
        baseline = run_baseline(result, doc_type_id)
    latency = time.perf_counter() - t0
    RequestLogger(LOG_PATH).write(
        log_record(
            request_id=uuid.uuid4().hex[:12],
            method=method,
            source_kind="pdf" if upload and upload[0].lower().endswith(".pdf") else "text",
            result=result,
            latency_s=latency,
            compare=bool(baseline),
            baseline=baseline,
        )
    )
    return {
        "method": method,
        "doc": {
            "source": result.source,
            "chars": result.doc_chars,
            "pages": result.page_count,
            "needs_ocr": result.needs_ocr,
        },
        "result": _result_dict(result),
        "baseline": _result_dict(baseline) if baseline else None,
        "latency_s": latency,
        "doc_text": result.doc_text,
    }


def run_via_api(
    *, text: str | None, upload: tuple[str, bytes] | None, method: str, doc_type_id: str, compare: bool
) -> dict[str, Any]:
    import requests

    if upload is not None:
        r = requests.post(
            f"{API_URL}/extract",
            files={"file": (upload[0], upload[1])},
            data={"method": method, "doc_type_id": doc_type_id, "compare": str(compare).lower()},
            timeout=600,
        )
    else:
        r = requests.post(
            f"{API_URL}/extract",
            json={"text": text, "method": method, "doc_type_id": doc_type_id, "compare": compare},
            timeout=600,
        )
    if r.status_code != 200:
        raise RuntimeError(f"API {r.status_code}: {r.text[:500]}")
    out: dict[str, Any] = r.json()
    return out


def _span_card(title: str, res: dict[str, Any] | None, doc_text: str | None) -> None:
    st.subheader(title)
    if res is None:
        st.info("not run")
        return
    ex, val = res["extraction"], res["validation"]
    span = ex.get("facts_span")
    prov = ex.get("provenance") or {}
    routing = prov.get("routing") or {}
    c1, c2, c3 = st.columns(3)
    c1.metric("span", f"[{span['start']}, {span['end']})" if span else "none")
    c2.metric("confidence", ex.get("confidence") or "—")
    c3.metric("validator", "OK" if val.get("ok") else "FAIL")
    if val.get("flags"):
        st.warning("flags: " + ", ".join(val["flags"]))
    if ex.get("notes"):
        st.caption("notes: " + ", ".join(ex["notes"]))
    meta = []
    if prov.get("model_id"):
        meta.append(f"model `{prov['model_id']}`")
    if prov.get("tier"):
        meta.append(
            f"tier **{prov['tier']}**" + (f" (trigger `{routing.get('trigger')}`)" if routing.get("trigger") else "")
        )
    if prov.get("input_tokens") is not None:
        meta.append(f"tokens {prov['input_tokens']}→{prov['output_tokens']}")
    if prov.get("cost_usd") is not None:
        meta.append(f"cost ${prov['cost_usd']:.3f}" + (" (CLI est.)" if prov.get("billing") == "subscription" else ""))
    if prov.get("latency_s") is not None:
        meta.append(f"latency {prov['latency_s']:.1f} s")
    if meta:
        st.markdown(" · ".join(meta))
    if span:
        preview = span["text"][:1500] + ("…" if len(span["text"]) > 1500 else "")
        st.text_area("facts span (preview)", preview, height=220, key=f"span_{title}")
    if ex.get("parties") or ex.get("procedural_posture"):
        st.markdown(f"**Parties:** {', '.join(ex.get('parties') or []) or '—'}")
        st.markdown(f"**Posture:** {ex.get('procedural_posture') or '—'}")
    if ex.get("key_events"):
        st.dataframe([{"date": e.get("date"), "event": e.get("text")} for e in ex["key_events"]], width="stretch")
    if ex.get("case_citations") or ex.get("record_citations"):
        st.markdown(
            f"**Case citations ({len(ex.get('case_citations') or [])}):** "
            + "; ".join(ex.get("case_citations") or [])[:800]
        )
        if ex.get("record_citations"):
            st.caption(f"record citations: {len(ex['record_citations'])} — " + "; ".join(ex["record_citations"])[:400])
    if val.get("citation_support") is not None:
        st.caption(
            f"citation fidelity {val.get('citation_fidelity')} · support {val.get('citation_support')} · "
            f"unsupported {val.get('n_unsupported_citations')}/{val.get('n_citations')}"
        )


def main() -> None:
    st.set_page_config(page_title="Legal facts extraction", layout="wide")
    st.title("Legal facts extraction — rules baseline vs LLM")
    st.caption(
        "Upload a U.S. court brief (PDF or text). Output is a schema-validated `FactsExtraction`; "
        "the LLM only ever sees the document inside a fixed prompt."
    )
    with st.sidebar:
        methods = sorted(EXTRACTORS)
        method = st.selectbox(
            "method", methods, index=methods.index(DEFAULT_METHOD) if DEFAULT_METHOD in methods else 0
        )
        compare = st.checkbox("compare with rules_v2", value=True)
        doc_type_id = st.text_input("doc_type_id", "UNKNOWN")
        mode = "API " + API_URL if API_URL else "in-process"
        st.caption(f"mode: {mode}")
        ok, detail = llm_available(BACKEND)
        st.caption(("LLM available — " if ok else "LLM unavailable — ") + detail)
    tab_up, tab_txt = st.tabs(["upload", "paste text"])
    with tab_up:
        up = st.file_uploader("PDF or .txt", type=["pdf", "txt"])
    with tab_txt:
        pasted = st.text_area("document text", height=200, key="pasted")
    if st.button("extract", type="primary", key="run"):
        if up is None and not pasted.strip():
            st.error("upload a file or paste text")
            return
        if method.startswith("llm-") and not ok and not API_URL:
            st.error(f"{method} needs an LLM backend: {detail}")
            return
        used = int(st.session_state.get("n_requests", 0))
        if used >= MAX_PER_SESSION:
            st.error(f"session limit reached ({MAX_PER_SESSION} extractions); reload the page to start a new session")
            return
        st.session_state["n_requests"] = used + 1
        upload = (up.name, up.getvalue()) if up is not None else None
        with st.spinner(f"running {method}…"):
            try:
                fn = run_via_api if API_URL else run_in_process
                out = fn(
                    text=None if upload else pasted,
                    upload=upload,
                    method=method,
                    doc_type_id=doc_type_id,
                    compare=compare,
                )
            except Exception as e:  # surfaced to the user, logged by the API/in-process logger
                st.error(f"{type(e).__name__}: {e}")
                return
        st.session_state["last"] = out
    last = st.session_state.get("last")
    if not last:
        return
    out = dict(last)
    d = out["doc"]
    st.markdown(
        f"**{d.get('source')}** · {d.get('chars'):,} chars · pages {d.get('pages')} · "
        f"needs_ocr {d.get('needs_ocr')} · {out['latency_s']:.1f} s"
    )
    left, right = st.columns(2)
    with left:
        _span_card(
            RULES_VERSION if out["method"] == RULES_VERSION else f"baseline: {RULES_VERSION}",
            out["baseline"] or (out["result"] if out["method"] == RULES_VERSION else None),
            out.get("doc_text"),
        )
    with right:
        _span_card(out["method"], out["result"] if out["method"] != RULES_VERSION else None, out.get("doc_text"))
    st.download_button(
        "download JSON",
        json.dumps({k: v for k, v in out.items() if k != "doc_text"}, indent=2),
        file_name="extraction.json",
        mime="application/json",
    )


def run() -> None:
    """Console entry: ``legallm-ui`` → ``streamlit run ui_app.py``."""
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(Path(__file__).resolve()), "--server.headless", "true"] + sys.argv[1:]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
