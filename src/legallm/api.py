"""C10 service: ``POST /extract`` (PDF or text) → ``FactsExtraction`` + validation; ``GET /health``.

    legallm-api [--host 0.0.0.0 --port 8000]          # uvicorn
    curl -F file=@brief.pdf -F method=llm-v3 http://localhost:8000/extract
    curl -H 'content-type: application/json' -d '{"text": "...", "method": "rules_v2"}' http://localhost:8000/extract

Every request is appended to a JSONL log (``LEGALLM_REQUEST_LOG``, default ``logs/requests.jsonl``): method,
model, prompt sha, tokens, cost, latency, validator flags, routing tier — never the document text. The document
text is untrusted input: it only ever reaches the model inside the user turn of a fixed prompt (see
``prompts.py``); the service adds no instructions from it and returns only schema-validated output.

Settings come from the environment (``LEGALLM_DEFAULT_METHOD``, ``LEGALLM_LLM_BACKEND``, ``LEGALLM_REQUEST_LOG``,
``LEGALLM_MAX_UPLOAD_MB``, ``LEGALLM_RATE_LIMIT_PER_MIN``); ``create_app(Settings(...))`` overrides them in code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from legallm import __version__
from legallm.baseline_adapter import RULES_VERSION
from legallm.guard import apply_guard
from legallm.llm_extractor import LlmExtractionError, configure_default
from legallm.single_doc import EXTRACTORS, NoTextError, SingleDocResult, extract_from_file, extract_from_text
from legallm.validators import validate_extraction

DEFAULT_LOG = Path("logs/requests.jsonl")


# ---------------------------------------------------------------------------
# Settings / availability
# ---------------------------------------------------------------------------


@dataclass
class Settings:
    default_method: str = os.environ.get("LEGALLM_DEFAULT_METHOD", "llm-v3")
    llm_backend: str = os.environ.get("LEGALLM_LLM_BACKEND", "api")
    request_log: Path = field(default_factory=lambda: Path(os.environ.get("LEGALLM_REQUEST_LOG", str(DEFAULT_LOG))))
    max_upload_mb: float = float(os.environ.get("LEGALLM_MAX_UPLOAD_MB", "20"))
    rate_limit_per_min: int = int(os.environ.get("LEGALLM_RATE_LIMIT_PER_MIN", "30"))
    compare_default: bool = True
    guard_mode: str = os.environ.get("LEGALLM_GUARD_MODE", "flag")  # "flag" | "block"


def run_baseline(result: SingleDocResult, doc_type_id: str = "UNKNOWN") -> SingleDocResult:
    """rules_v2 on the *same* ``doc_text`` the main result's offsets refer to (no re-normalisation)."""
    t0 = time.perf_counter()
    ex = EXTRACTORS[RULES_VERSION](result.doc_text, doc_type_id)
    rep = apply_guard(validate_extraction(ex, result.doc_text, require_facts=False), result.doc_text, ex)
    return SingleDocResult(
        source=result.source,
        method=RULES_VERSION,
        doc_type_id=doc_type_id,
        text_extractor=result.text_extractor,
        text_notes=list(result.text_notes),
        page_count=result.page_count,
        needs_ocr=result.needs_ocr,
        ocr_reasons=list(result.ocr_reasons),
        doc_chars=result.doc_chars,
        extraction=ex,
        validation=rep,
        elapsed_s=time.perf_counter() - t0,
        doc_text=result.doc_text,
    )


def llm_available(backend: str) -> tuple[bool, str]:
    """Can an ``llm-*`` method run under this backend? (No network is touched.)"""
    if backend == "claude-cli":
        try:
            from legallm.claude_cli import find_claude_exe

            return True, f"claude-cli: {find_claude_exe()}"
        except Exception as e:  # not installed / not on PATH
            return False, f"claude-cli unavailable: {e}"
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True, "api: credentials in env"
    return False, "api: no ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN in env"


# ---------------------------------------------------------------------------
# Request log (JSONL, no document text)
# ---------------------------------------------------------------------------


class RequestLogger:
    def __init__(self, path: Path | None):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()

    def write(self, record: dict[str, Any]) -> None:
        if self.path is None:
            return
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")


def log_record(
    *,
    request_id: str,
    method: str,
    source_kind: str,
    result: SingleDocResult | None,
    latency_s: float,
    error: str | None = None,
    doc_chars: int | None = None,
    doc_sha1: str | None = None,
    compare: bool = False,
    baseline: SingleDocResult | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "request_id": request_id,
        "method": method,
        "source_kind": source_kind,
        "doc_chars": doc_chars if doc_chars is not None else (result.doc_chars if result else None),
        "doc_sha1": doc_sha1,
        "latency_s": round(latency_s, 3),
        "error": error,
        "compare": compare,
    }
    if result is not None:
        ex, rep, prov = result.extraction, result.validation, result.extraction.provenance or {}
        routing = prov.get("routing") or {}
        rec.update(
            {
                "pages": result.page_count,
                "text_extractor": result.text_extractor,
                "needs_ocr": result.needs_ocr,
                "extractor_version": ex.extractor_version,
                "model_id": prov.get("model_id"),
                "prompt_sha": prov.get("prompt_sha"),
                "backend": prov.get("backend", "local"),
                "tier": prov.get("tier"),
                "trigger": routing.get("trigger"),
                "escalated": routing.get("escalated"),
                "input_tokens": prov.get("input_tokens"),
                "output_tokens": prov.get("output_tokens"),
                "cost_usd": prov.get("cost_usd"),
                "model_latency_s": prov.get("latency_s"),
                "span_found": ex.facts_span is not None,
                "span": [ex.facts_span.start, ex.facts_span.end] if ex.facts_span else None,
                "confidence": ex.confidence,
                "notes": list(ex.notes),
                "validation_ok": rep.ok,
                "flags": list(rep.flags),
                "citation_fidelity": rep.citation_fidelity,
                "citation_support": rep.citation_support,
                "n_case_citations": len(ex.case_citations),
                "n_key_events": len(ex.key_events),
            }
        )
    if baseline is not None:
        bex = baseline.extraction
        rec["baseline"] = {
            "method": baseline.method,
            "span": [bex.facts_span.start, bex.facts_span.end] if bex.facts_span else None,
            "confidence": bex.confidence,
            "validation_ok": baseline.validation.ok,
        }
    return rec


# ---------------------------------------------------------------------------
# Rate limit (in-memory sliding window per client)
# ---------------------------------------------------------------------------


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, client: str, now: float | None = None) -> bool:
        if self.per_minute <= 0:
            return True
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[client]
            while q and now - q[0] > 60.0:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            return True


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ExtractTextRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Document text (already extracted from the PDF)")
    method: str | None = None
    doc_type_id: str = "UNKNOWN"
    compare: bool | None = Field(None, description="also run the rules_v2 baseline (default: server setting)")


class DocInfo(BaseModel):
    source: str
    kind: str  # "pdf" | "text"
    chars: int
    pages: int | None
    text_extractor: str
    needs_ocr: bool
    ocr_reasons: list[str]
    sha1: str


class MethodResult(BaseModel):
    method: str
    extraction: dict[str, Any]
    validation: dict[str, Any]
    elapsed_s: float


class ExtractResponse(BaseModel):
    request_id: str
    method: str
    doc: DocInfo
    result: MethodResult
    baseline: MethodResult | None = None
    latency_s: float


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _method_result(r: SingleDocResult) -> MethodResult:
    return MethodResult(
        method=r.method,
        extraction=r.extraction.model_dump(),
        validation=r.validation.to_dict(),
        elapsed_s=round(r.elapsed_s, 3),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or Settings()
    if s.llm_backend:
        configure_default(backend=s.llm_backend)
    logger = RequestLogger(s.request_log)
    limiter = RateLimiter(s.rate_limit_per_min)
    app = FastAPI(
        title="Legal facts extraction service",
        version=__version__,
        description="Extract the Statement of Facts (span + structured fields) from a U.S. court brief; "
        "rules_v2 baseline or Claude extractors with deterministic validators.",
    )
    app.state.settings = s
    app.state.request_logger = logger

    @app.get("/health")
    def health() -> dict[str, Any]:
        ok, detail = llm_available(s.llm_backend)
        return {
            "status": "ok",
            "version": __version__,
            "default_method": s.default_method,
            "methods": sorted(EXTRACTORS),
            "llm_backend": s.llm_backend,
            "llm_available": ok,
            "llm_detail": detail,
            "request_log": str(s.request_log) if s.request_log else None,
            "guard_mode": s.guard_mode,
        }

    @app.get("/methods")
    def methods() -> dict[str, Any]:
        return {"methods": sorted(EXTRACTORS), "default": s.default_method, "baseline": RULES_VERSION}

    @app.post("/extract", response_model=ExtractResponse)
    async def extract(request: Request) -> Any:
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client):
            raise HTTPException(status_code=429, detail=f"rate limit: {s.rate_limit_per_min} requests/minute")
        request_id = uuid.uuid4().hex[:12]
        t0 = time.perf_counter()
        ctype = request.headers.get("content-type", "")
        method = s.default_method
        compare = s.compare_default
        doc_type_id = "UNKNOWN"
        source_kind = "text"
        tmp_path: Path | None = None
        text: str | None = None
        filename = "<text>"
        try:
            if ctype.startswith("multipart/form-data"):
                form = await request.form()
                upload = form.get("file")
                if upload is None or not hasattr(upload, "read"):
                    raise HTTPException(status_code=422, detail="multipart request needs a 'file' field")
                method = str(form.get("method") or method)
                doc_type_id = str(form.get("doc_type_id") or doc_type_id)
                if form.get("compare") is not None:
                    compare = str(form.get("compare")).lower() in ("1", "true", "yes", "on")
                data = await upload.read()
                if len(data) > s.max_upload_mb * 1024 * 1024:
                    raise HTTPException(status_code=413, detail=f"upload exceeds {s.max_upload_mb} MB")
                filename = str(getattr(upload, "filename", "") or "upload")
                suffix = Path(filename).suffix.lower() or ".txt"
                if suffix == ".pdf":
                    source_kind = "pdf"
                    fd, name = tempfile.mkstemp(suffix=".pdf", prefix="legallm_")
                    os.close(fd)
                    tmp_path = Path(name)
                    tmp_path.write_bytes(data)
                else:
                    text = data.decode("utf-8", errors="replace")
            else:
                try:
                    body = ExtractTextRequest.model_validate(await request.json())
                except ValueError as e:
                    raise HTTPException(status_code=422, detail=f"invalid JSON body: {e}") from e
                except Exception as e:  # pydantic validation
                    raise HTTPException(status_code=422, detail=str(e)) from e
                method = body.method or method
                doc_type_id = body.doc_type_id
                if body.compare is not None:
                    compare = body.compare
                text = body.text
            if method not in EXTRACTORS:
                raise HTTPException(status_code=400, detail=f"unknown method {method!r}; known: {sorted(EXTRACTORS)}")
            if method.startswith("llm-"):
                ok, detail = llm_available(s.llm_backend)
                if not ok:
                    raise HTTPException(status_code=503, detail=f"LLM methods unavailable ({detail}); use rules_v2")
            if text is not None and not text.strip():
                raise HTTPException(status_code=422, detail="empty document text")

            try:
                if tmp_path is not None:
                    result = extract_from_file(tmp_path, method=method, doc_type_id=doc_type_id, require_facts=False)
                    result.source = filename
                else:
                    assert text is not None
                    result = extract_from_text(
                        text, method=method, doc_type_id=doc_type_id, source=filename, require_facts=False
                    )
                if s.guard_mode == "block" and not result.validation.checks.get("injection_not_suspected", True):
                    pats = [f for f in result.validation.flags if f.startswith("injection_suspected:")]
                    raise HTTPException(
                        status_code=422, detail=f"document refused: prompt-injection suspected ({', '.join(pats)})"
                    )
                baseline: SingleDocResult | None = None
                if compare and method != RULES_VERSION:
                    baseline = run_baseline(result, doc_type_id)
            except NoTextError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
            except LlmExtractionError as e:
                raise HTTPException(status_code=502, detail=f"extractor failed: {e}") from e
            except KeyError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e

            latency = time.perf_counter() - t0
            sha = _sha1(result.doc_text)
            logger.write(
                log_record(
                    request_id=request_id,
                    method=method,
                    source_kind=source_kind,
                    result=result,
                    latency_s=latency,
                    doc_sha1=sha,
                    compare=bool(baseline),
                    baseline=baseline,
                )
            )
            return ExtractResponse(
                request_id=request_id,
                method=method,
                doc=DocInfo(
                    source=result.source,
                    kind=source_kind,
                    chars=result.doc_chars,
                    pages=result.page_count,
                    text_extractor=result.text_extractor,
                    needs_ocr=result.needs_ocr,
                    ocr_reasons=result.ocr_reasons,
                    sha1=sha,
                ),
                result=_method_result(result),
                baseline=_method_result(baseline) if baseline else None,
                latency_s=round(latency, 3),
            )
        except HTTPException as e:
            logger.write(
                log_record(
                    request_id=request_id,
                    method=method,
                    source_kind=source_kind,
                    result=None,
                    latency_s=time.perf_counter() - t0,
                    error=f"{e.status_code}: {e.detail}",
                    doc_chars=len(text) if text else None,
                )
            )
            raise
        except Exception as e:  # pragma: no cover - defensive
            logger.write(
                log_record(
                    request_id=request_id,
                    method=method,
                    source_kind=source_kind,
                    result=None,
                    latency_s=time.perf_counter() - t0,
                    error=f"500: {type(e).__name__}: {e}",
                )
            )
            return JSONResponse(
                status_code=500, content={"detail": f"{type(e).__name__}: {e}", "request_id": request_id}
            )
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    return app


app = create_app()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="legallm-api", description="Serve the facts extraction API (uvicorn).")
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    ap.add_argument("--reload", action="store_true")
    args = ap.parse_args(argv)
    import uvicorn

    uvicorn.run("legallm.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
