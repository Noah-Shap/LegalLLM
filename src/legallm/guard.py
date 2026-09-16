"""C15 prompt-injection guard: the document is untrusted input.

Structural isolation already holds: the system prompt is fixed per version (``prompts.py``), the document only
ever appears inside the user turn, output is schema-constrained JSON, and every span is re-located in the
document text (anchors) with citations checked verbatim against it. This module adds the two things structure
cannot give:

1. **Detection** — ``scan_text`` flags instruction-like passages in the document (\"ignore previous
   instructions\", chat-template tokens, \"system prompt\", \"set has_facts to\", …) and invisible-character runs
   used to hide them. A hit is reported as a validator flag ``injection_suspected:<pattern>``; extraction still
   runs (the facts are still the facts) unless the service is configured to block.
2. **Output containment** — ``scan_output`` checks the free-text fields the model wrote (parties, posture, key
   events, notes) for the same patterns. Injected text that made it into the output fails validation
   (``injection_in_output:<field>``), because that is the model following the document instead of the prompt.

``apply_guard`` folds both into a ``ValidationReport`` and is called on every extraction (``single_doc``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from legallm.schema import FactsExtraction
from legallm.validators import ValidationReport

INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_previous",
        re.compile(
            r"\b(ignore|disregard|forget|override)\s+(all\s+|any\s+)?(the\s+|your\s+)?(previous|prior|above|earlier|preceding|"
            r"system)\s+(instructions?|prompts?|directions?|rules?|guidance)\b",
            re.I,
        ),
    ),
    ("role_reassignment", re.compile(r"\byou are (now )?(a|an|the) (helpful|ai|assistant|language model|new)\b", re.I)),
    ("system_prompt_ref", re.compile(r"\b(system prompt|developer message|hidden instructions?)\b", re.I)),
    (
        "chat_template_token",
        re.compile(r"<\|im_start\|>|<\|im_end\|>|<\|system\|>|<\|user\|>|<\|assistant\|>|\[INST\]|<<SYS>>", re.I),
    ),
    ("role_line", re.compile(r"^\s*(assistant|system)\s*:\s*\S", re.I | re.M)),
    ("instruction_header", re.compile(r"^\s*#{1,6}\s*(instructions?|system|prompt)\b", re.I | re.M)),
    (
        "forced_output",
        re.compile(
            r"\b(output|return|respond with|reply with|print|emit)\s+(only\s+)?"
            r"(the following|this exact|exactly this)\b",
            re.I,
        ),
    ),
    (
        "schema_tampering",
        re.compile(r"\b(set|make|report)\s+has_facts\s+(to|as|=)|facts_(start|end)_anchor\b|\bdo not extract\b", re.I),
    ),
    ("ai_self_reference", re.compile(r"\bas an ai( language)? model\b", re.I)),
    (
        "prompt_exfiltration",
        re.compile(r"\b(reveal|print|show|repeat|leak)\s+(your|the)\s+(system\s+)?(prompt|instructions)\b", re.I),
    ),
]

# zero-width and bidi-control characters used to hide instructions from human readers
INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")
OUTPUT_FIELDS = ("parties", "procedural_posture", "key_events", "notes", "record_citations", "case_citations")


@dataclass
class GuardMatch:
    pattern: str
    offset: int
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return {"pattern": self.pattern, "offset": self.offset, "snippet": self.snippet}


@dataclass
class GuardReport:
    suspected: bool = False
    matches: list[GuardMatch] = field(default_factory=list)
    invisible_chars: int = 0
    output_hits: list[str] = field(default_factory=list)  # "<field>:<pattern>"

    @property
    def patterns(self) -> list[str]:
        seen: list[str] = []
        for m in self.matches:
            if m.pattern not in seen:
                seen.append(m.pattern)
        return seen

    def to_dict(self) -> dict[str, Any]:
        return {
            "suspected": self.suspected,
            "patterns": self.patterns,
            "matches": [m.to_dict() for m in self.matches],
            "invisible_chars": self.invisible_chars,
            "output_hits": list(self.output_hits),
        }


def scan_text(doc_text: str, *, max_matches: int = 20, invisible_threshold: int = 20) -> GuardReport:
    """Flag instruction-like passages and hidden-character runs in an untrusted document."""
    rep = GuardReport()
    if not doc_text:
        return rep
    for name, rx in INJECTION_PATTERNS:
        for m in rx.finditer(doc_text):
            if len(rep.matches) >= max_matches:
                break
            a, b = max(0, m.start() - 40), min(len(doc_text), m.end() + 40)
            rep.matches.append(GuardMatch(name, m.start(), doc_text[a:b].replace("\n", " ")))
    rep.invisible_chars = len(INVISIBLE.findall(doc_text))
    if rep.invisible_chars >= invisible_threshold:
        rep.matches.append(GuardMatch("invisible_characters", -1, f"{rep.invisible_chars} zero-width/bidi chars"))
    rep.suspected = bool(rep.matches)
    return rep


def _field_texts(extraction: FactsExtraction) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name in OUTPUT_FIELDS:
        val = getattr(extraction, name, None)
        if val is None:
            continue
        if isinstance(val, str):
            out.append((name, val))
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    out.append((name, item))
                else:  # KeyEvent
                    for attr in ("text", "date"):
                        v = getattr(item, attr, None)
                        if isinstance(v, str):
                            out.append((name, v))
    return out


def scan_output(extraction: FactsExtraction) -> list[str]:
    """Injection patterns that made it into the model's free-text fields (span text excluded: it is a copy)."""
    hits: list[str] = []
    for name, text in _field_texts(extraction):
        for pname, rx in INJECTION_PATTERNS:
            if rx.search(text):
                key = f"{name}:{pname}"
                if key not in hits:
                    hits.append(key)
    return hits


def apply_guard(report: ValidationReport, doc_text: str, extraction: FactsExtraction) -> ValidationReport:
    """Add guard checks/flags to a validation report. Output contamination fails ``ok``; document suspicion warns."""
    g = scan_text(doc_text)
    g.output_hits = scan_output(extraction)
    report.checks["injection_not_suspected"] = not g.suspected
    report.checks["no_injection_in_output"] = not g.output_hits
    for p in g.patterns:
        report.flags.append(f"injection_suspected:{p}")
    for h in g.output_hits:
        report.flags.append(f"injection_in_output:{h}")
    if g.output_hits:
        report.ok = False
    return report
