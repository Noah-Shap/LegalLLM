"""Record / replay clients: canned model responses keyed by the exact request, for the offline CI gate.

A recorded response is keyed by ``sha256(model | system prompt | user turn)`` — i.e. the model, the prompt
version and the document — so a prompt or model change invalidates the recording (re-record with
``legallm-gate --record``), while any change to the code *after* the model (anchor location, validators,
routing, schema parsing) is exercised on every replay. That is the property the gate needs: it must fail
when that code regresses, which a cache of finished extractions cannot do.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from legallm.llm_extractor import LlmExtractionError


class ReplayError(LlmExtractionError):
    """No recorded response for this request."""


def request_key(req: dict[str, Any]) -> str:
    system = req.get("system")
    if isinstance(system, list):
        system_text = "\n".join(str(b.get("text", "")) for b in system if isinstance(b, dict))
    else:
        system_text = str(system or "")
    user = ""
    for m in req.get("messages", []):
        if m.get("role") == "user":
            c = m.get("content")
            user += c if isinstance(c, str) else json.dumps(c, sort_keys=True)
    payload = f"{req.get('model')}|{system_text}|{user}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def response_from(rec: dict[str, Any]) -> Any:
    usage = rec.get("usage")
    return SimpleNamespace(
        model=rec.get("model"),
        stop_reason=rec.get("stop_reason", "end_turn"),
        stop_details=None,
        _request_id=None,
        content=[SimpleNamespace(type="text", text=rec["text"])],
        usage=SimpleNamespace(**usage) if isinstance(usage, dict) else None,
        replayed=True,
    )


class _ReplayMessages:
    def __init__(self, store: dict[str, dict[str, Any]]):
        self.store = store
        self.hits: list[str] = []

    def create(self, **req: Any) -> Any:
        key = request_key(req)
        rec = self.store.get(key)
        if rec is None:
            raise ReplayError(
                f"no recorded response for model={req.get('model')} key={key} "
                f"({len(self.store)} recordings loaded); re-record with `legallm-gate --record`"
            )
        self.hits.append(key)
        return response_from(rec)


class ReplayClient:
    """``.messages.create(**req)`` served from recordings; raises ``ReplayError`` on a miss."""

    def __init__(self, store: dict[str, dict[str, Any]]):
        self.messages = _ReplayMessages(store)


class _RecordingMessages:
    def __init__(self, inner: Any, store: dict[str, dict[str, Any]]):
        self.inner = inner
        self.store = store

    def create(self, **req: Any) -> Any:
        from legallm.llm_extractor import LlmExtractor

        res = self.inner.messages.create(**req)
        usage = getattr(res, "usage", None)
        rec: dict[str, Any] = {
            "key": request_key(req),
            "model": getattr(res, "model", req.get("model")),
            "requested_model": req.get("model"),
            "stop_reason": getattr(res, "stop_reason", "end_turn"),
            "text": LlmExtractor._response_text(res),
            "usage": (
                {
                    k: getattr(usage, k, None)
                    for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
                }
                if usage is not None
                else None
            ),
        }
        cli = getattr(res, "cli", None)
        if isinstance(cli, dict) and cli.get("total_cost_usd") is not None:
            rec["cli_cost_usd"] = cli["total_cost_usd"]
        self.store[rec["key"]] = rec
        return res


class RecordingClient:
    """Wraps a real client; every response is stored under its request key."""

    def __init__(self, inner: Any, store: dict[str, dict[str, Any]]):
        self.messages = _RecordingMessages(inner, store)


def load_responses(path: Path) -> dict[str, dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return {}
    store: dict[str, dict[str, Any]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            store[rec["key"]] = rec
    return store


def save_responses(path: Path, store: dict[str, dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for key in sorted(store):
            f.write(json.dumps(store[key], ensure_ascii=False) + "\n")
