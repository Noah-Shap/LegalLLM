"""Gold set manifest + labels (intent.md §5, C5).

    legallm-gold init      build evals/gold/gold_v1.jsonl from the audit parquet + 20 no_facts_span failures
    legallm-gold verify    recompute doc_text for every record and check the rules span still matches
    legallm-gold stats     labeling progress by source / stratum
    legallm-gold label     launch the Streamlit labeler (pip install -e ".[label]")

What is tracked in git: ids, strata, rules-extractor spans, and human labels
(rating, corrected gold span offsets, notes). Never the brief text — offsets
refer to ``preprocess_text(normalize_text(raw))`` of the local PDF, and every
record carries ``doc_sha1`` of that text so drift is detectable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

GOLD_VERSION = "v1"
DEFAULT_GOLD_PATH = Path("evals/gold") / f"gold_{GOLD_VERSION}.jsonl"
DEFAULT_AUDIT_PARQUET = Path("data/processed/gold_audit_set.parquet")
DEFAULT_FAILURES_JSONL = Path("data/processed/facts_failures_2k.jsonl")
DEFAULT_PDF_DIR = Path("data/raw/pdfs")

Rating = Literal["correct", "partially_correct", "incorrect"]
Source = Literal["audit_set", "no_facts_span"]
Status = Literal["pending", "labeled", "skipped"]


class GoldLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: Rating | None = Field(default=None, description="Rubric rating of the rules_v2 span (audit_set docs).")
    has_facts: bool | None = Field(default=None, description="Does the brief contain a facts section at all?")
    gold_span: list[int] | None = Field(
        default=None, description="Human-corrected [start, end) into doc_text; null if not corrected / no facts."
    )
    notes: str = ""
    labeled_at: str | None = None
    labeler: str | None = None


class GoldRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gold_id: str
    search_result_id: int
    source: Source
    pdf_path: str
    pdf_url: str | None = None
    doc_type_id: str = "UNKNOWN"
    stratum: dict[str, str] = Field(default_factory=dict)
    rules_span: list[int] | None = None
    rules_confidence: str | None = None
    rules_notes: str | None = None
    rules_method: str | None = None
    doc_sha1: str | None = None
    doc_chars: int | None = None
    label: GoldLabel = Field(default_factory=GoldLabel)
    status: Status = "pending"
    suggestion: dict[str, Any] | None = Field(
        default=None,
        description="LLM-judge pre-label (legallm-gold prefill): ratings, issues, suggested span. Never ground truth.",
    )

    @property
    def is_human_labeled(self) -> bool:
        return self.status == "labeled" and not (self.label.labeler or "").startswith("judge:")

    @property
    def effective_span(self) -> list[int] | None:
        """Gold span if corrected, else the rules span (audit_set) — what evals compare against."""
        if self.label.gold_span is not None:
            return self.label.gold_span
        if self.label.has_facts is False:
            return None
        return self.rules_span


# ---------------------------------------------------------------------------
# Manifest build
# ---------------------------------------------------------------------------


def doc_sha1(doc_text: str) -> str:
    return hashlib.sha1(doc_text.encode("utf-8")).hexdigest()[:16]


def build_manifest(
    audit_parquet: Path = DEFAULT_AUDIT_PARQUET,
    failures_jsonl: Path = DEFAULT_FAILURES_JSONL,
    pdf_dir: Path = DEFAULT_PDF_DIR,
    *,
    n_failures: int = 20,
    seed: int = 42,
) -> list[GoldRecord]:
    """Seed records: every audit-set row + ``n_failures`` random no_facts_span failures with a local PDF."""
    import pandas as pd

    records: list[GoldRecord] = []
    df = pd.read_parquet(audit_parquet)
    for i, row in enumerate(df.itertuples(index=False), start=1):
        sid = int(row.search_result_id)
        records.append(
            GoldRecord(
                gold_id=f"g{i:03d}",
                search_result_id=sid,
                source="audit_set",
                pdf_path=(pdf_dir / f"{sid}.pdf").as_posix(),
                pdf_url=getattr(row, "pdf_url", None),
                doc_type_id=str(getattr(row, "doc_type_id", "UNKNOWN")),
                stratum={
                    "confidence": str(getattr(row, "extractor_confidence", "")),
                    "len_bin": str(getattr(row, "len_bin", "")),
                },
                rules_span=[int(row.facts_start), int(row.facts_end)],
                rules_confidence=str(getattr(row, "extractor_confidence", "")) or None,
                rules_notes=str(getattr(row, "extractor_notes", "")) or None,
                rules_method=str(getattr(row, "extractor_method", "")) or None,
            )
        )

    seen = {r.search_result_id for r in records}
    failures: list[dict[str, Any]] = []
    with open(failures_jsonl, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            sid = rec.get("search_id")
            if rec.get("reason") != "no_facts_span" or sid is None or int(sid) in seen:
                continue
            if not (pdf_dir / f"{int(sid)}.pdf").exists():
                continue
            failures.append(rec)
    failures.sort(key=lambda r: int(r["search_id"]))
    rng = random.Random(seed)
    for j, rec in enumerate(rng.sample(failures, min(n_failures, len(failures))), start=1):
        sid = int(rec["search_id"])
        records.append(
            GoldRecord(
                gold_id=f"f{j:03d}",
                search_result_id=sid,
                source="no_facts_span",
                pdf_path=(pdf_dir / f"{sid}.pdf").as_posix(),
                pdf_url=rec.get("pdf_url"),
                stratum={"confidence": "none", "len_bin": "n/a"},
                rules_span=None,
                rules_confidence=None,
                rules_notes=";".join(rec.get("notes") or []) or None,
                rules_method="rules_v2",
            )
        )
    return records


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def load_gold(path: Path = DEFAULT_GOLD_PATH) -> list[GoldRecord]:
    out: list[GoldRecord] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(GoldRecord.model_validate_json(line))
    return out


def save_gold(records: list[GoldRecord], path: Path = DEFAULT_GOLD_PATH) -> Path:
    """Atomic rewrite (temp file + replace) so a crash mid-save never truncates labels."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(r.model_dump_json(exclude_none=False) + "\n")
    os.replace(tmp, path)
    return path


def write_meta(path: Path, records: list[GoldRecord], *, seed: int, n_failures: int) -> Path:
    meta = {
        "gold_version": GOLD_VERSION,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seed": seed,
        "n_audit_set": sum(r.source == "audit_set" for r in records),
        "n_no_facts_span": sum(r.source == "no_facts_span" for r in records),
        "n_failures_requested": n_failures,
        "offset_contract": "preprocess_text(normalize_text(raw_pdf_text)); see legallm.baseline_adapter",
    }
    meta_path = path.with_name(path.stem + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta_path


# ---------------------------------------------------------------------------
# Verification against the live document text
# ---------------------------------------------------------------------------


def document_text(pdf_path: str | Path) -> str:
    """The exact text every span offset refers to (same path as legallm-extract)."""
    from legallm.single_doc import extract_from_file

    return extract_from_file(pdf_path, method="rules_v2", require_facts=False).doc_text


def verify_record(rec: GoldRecord, doc_text: str) -> list[str]:
    """Return problems (empty list = OK). Fills doc_sha1/doc_chars if missing."""
    problems: list[str] = []
    sha = doc_sha1(doc_text)
    if rec.doc_sha1 is None:
        rec.doc_sha1 = sha
        rec.doc_chars = len(doc_text)
    elif rec.doc_sha1 != sha:
        problems.append(f"doc_sha1 changed {rec.doc_sha1} -> {sha} (text extraction drift)")
    for name, span in (("rules_span", rec.rules_span), ("gold_span", rec.label.gold_span)):
        if span is None:
            continue
        s, e = span
        if not (0 <= s < e <= len(doc_text)):
            problems.append(f"{name} {span} out of bounds for {len(doc_text)} chars")
    return problems


def verify_all(records: list[GoldRecord], *, progress: bool = False) -> dict[str, list[str]]:
    problems: dict[str, list[str]] = {}
    for i, rec in enumerate(records, start=1):
        if progress:
            print(f"  [{i}/{len(records)}] {rec.gold_id} {rec.search_result_id}", file=sys.stderr, end="\r")
        try:
            text = document_text(rec.pdf_path)
        except Exception as e:  # missing pdf, no text
            problems[rec.gold_id] = [f"{type(e).__name__}: {e}"]
            continue
        p = verify_record(rec, text)
        if p:
            problems[rec.gold_id] = p
    if progress:
        print(file=sys.stderr)
    return problems


# ---------------------------------------------------------------------------
# Labeling
# ---------------------------------------------------------------------------


def set_label(
    rec: GoldRecord,
    *,
    rating: Rating | None,
    has_facts: bool | None,
    gold_span: list[int] | None,
    notes: str = "",
    labeler: str = "noah",
    status: Status = "labeled",
) -> GoldRecord:
    if gold_span is not None:
        s, e = int(gold_span[0]), int(gold_span[1])
        if e <= s or s < 0:
            raise ValueError(f"gold_span must satisfy 0 <= start < end, got {gold_span}")
        gold_span = [s, e]
    rec.label = GoldLabel(
        rating=rating,
        has_facts=has_facts,
        gold_span=gold_span,
        notes=notes or "",
        labeled_at=datetime.now(UTC).isoformat(timespec="seconds"),
        labeler=labeler,
    )
    rec.status = status
    return rec


# ---------------------------------------------------------------------------
# Judge pre-labels (legallm-judge verdicts -> suggestions -> optional bulk accept)
# ---------------------------------------------------------------------------

POLICIES: tuple[str, ...] = ("nonbrief", "rules_correct", "llm_correct", "corrected")


def load_verdicts(path: Path) -> dict[str, dict[str, Any]]:
    """{gold_id: verdict dict} from a legallm-judge JSONL."""
    out: dict[str, dict[str, Any]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                v = json.loads(line)
                out[v["gold_id"]] = v
    return out


def suggestion_from_verdict(v: dict[str, Any], run_name: str) -> dict[str, Any] | None:
    """Reduce a judge verdict to what the labeler and the accept policies need."""
    if v.get("error"):
        return None
    cands = {v["method_a"]: ("a", v["span_a"]), v["method_b"]: ("b", v["span_b"])}
    rules = cands.get("rules_v2")
    llm = next(((m, x[1]) for m, x in cands.items() if m.startswith("llm")), None)
    has_facts = bool(v.get("is_brief_with_facts"))
    corrected = v.get("corrected_span")
    ratings = {m: v[f"rating_{ab}"] for m, (ab, _) in cands.items()}
    issues = {m: v[f"issues_{ab}"] for m, (ab, _) in cands.items()}
    comments = {m: v[f"comment_{ab}"] for m, (ab, _) in cands.items()}
    suggested_span: list[int] | None = None
    basis = "none"
    if has_facts:
        if corrected:
            suggested_span, basis = corrected, "judge_corrected"
        elif rules and ratings.get("rules_v2") == "correct" and rules[1]:
            suggested_span, basis = rules[1], "rules_span"
        else:
            for m, (_, span) in cands.items():
                if m.startswith("llm") and ratings.get(m) == "correct" and span:
                    suggested_span, basis = span, f"{m}_span"
                    break
    return {
        "judge_model": v.get("judge_model"),
        "judge_version": v.get("judge_version"),
        "judge_run": run_name,
        "document_kind": v.get("document_kind"),
        "has_facts": has_facts,
        "ratings": ratings,
        "issues": issues,
        "comments": comments,
        "preferred": v.get("preferred"),
        "confidence": v.get("confidence"),
        "summary": v.get("summary", ""),
        "rules_rating": ratings.get("rules_v2"),
        "suggested_span": suggested_span,
        "span_basis": basis,
        "corrected_notes": v.get("corrected_notes") or [],
        "llm_method": llm[0] if llm else None,
    }


def prefill(
    records: list[GoldRecord], verdicts: dict[str, dict[str, Any]], run_name: str, *, overwrite: bool = False
) -> dict[str, int]:
    """Attach judge suggestions to records (pending ones by default). Never touches labels."""
    n_set = n_skip = n_missing = 0
    for rec in records:
        v = verdicts.get(rec.gold_id)
        if v is None:
            n_missing += 1
            continue
        if rec.suggestion is not None and not overwrite:
            n_skip += 1
            continue
        s = suggestion_from_verdict(v, run_name)
        if s is None:
            n_missing += 1
            continue
        rec.suggestion = s
        n_set += 1
    return {"set": n_set, "skipped_existing": n_skip, "missing_or_errored": n_missing}


def accept_policy(rec: GoldRecord, policies: set[str], min_confidence: str = "high") -> str | None:
    """Which accept policy (if any) applies to a pending record with a suggestion."""
    s = rec.suggestion
    if s is None or rec.status != "pending":
        return None
    order = {"low": 0, "medium": 1, "high": 2}
    if order.get(s.get("confidence") or "low", 0) < order.get(min_confidence, 2):
        return None
    if "nonbrief" in policies and s["has_facts"] is False:
        return "nonbrief"
    if s["has_facts"] and s.get("suggested_span"):
        basis = s.get("span_basis") or ""
        if "rules_correct" in policies and basis == "rules_span":
            return "rules_correct"
        if "llm_correct" in policies and basis.endswith("_span") and basis.startswith("llm"):
            return "llm_correct"
        if "corrected" in policies and basis == "judge_corrected":
            return "corrected"
    return None


def accept_judge(
    records: list[GoldRecord],
    *,
    policies: set[str],
    min_confidence: str = "high",
    dry_run: bool = False,
) -> dict[str, int]:
    """Bulk-accept judge suggestions as labels (labeler='judge:<model>'). Human labels are never overwritten."""
    counts: Counter[str] = Counter()
    for rec in records:
        pol = accept_policy(rec, policies, min_confidence)
        if pol is None:
            continue
        counts[pol] += 1
        if dry_run:
            continue
        s = rec.suggestion or {}
        rules_rating = s.get("rules_rating")
        if pol == "nonbrief":
            rating = ("incorrect" if rec.rules_span else None) if rec.source == "audit_set" else None
            set_label(
                rec,
                rating=rating if rating in ("correct", "partially_correct", "incorrect") else None,  # type: ignore[arg-type]
                has_facts=False,
                gold_span=None,
                notes=f"[judge:{pol}] {s.get('document_kind')}: {s.get('summary', '')}",
                labeler=f"judge:{s.get('judge_model')}",
            )
        else:
            set_label(
                rec,
                rating=rules_rating if rec.rules_span else None,  # type: ignore[arg-type]
                has_facts=True,
                gold_span=s.get("suggested_span"),
                notes=f"[judge:{pol}] {s.get('summary', '')}",
                labeler=f"judge:{s.get('judge_model')}",
            )
    return dict(counts)


def stats(records: list[GoldRecord]) -> dict[str, Any]:
    by_status = Counter(r.status for r in records)
    by_source = Counter((r.source, r.status) for r in records)
    ratings = Counter(r.label.rating for r in records if r.label.rating)
    by_labeler = Counter(("human" if r.is_human_labeled else "judge") for r in records if r.status == "labeled")
    with_suggestion = sum(r.suggestion is not None for r in records)

    def _is_corrected(r: GoldRecord) -> bool:
        return r.label.gold_span is not None and r.label.gold_span != r.rules_span

    corrected = sum(_is_corrected(r) for r in records)
    corrected_lowmed = sum(_is_corrected(r) and r.stratum.get("confidence") in ("low", "medium") for r in records)
    with_gold_span = sum(r.label.gold_span is not None for r in records)
    return {
        "total": len(records),
        "by_status": dict(by_status),
        "by_source_status": {f"{s}/{st}": n for (s, st), n in sorted(by_source.items())},
        "ratings": dict(ratings),
        "by_labeler": dict(by_labeler),
        "with_suggestion": with_suggestion,
        "with_gold_span": with_gold_span,
        "boundary_corrected": corrected,
        "boundary_corrected_low_medium": corrected_lowmed,
        "targets": {"rated_audit_set": 100, "boundary_corrected": 40, "failures_located": 20},
    }


def format_stats(st: dict[str, Any]) -> str:
    lines = [f"total: {st['total']}", f"by_status: {st['by_status']}", f"by_source/status: {st['by_source_status']}"]
    lines.append(f"ratings: {st['ratings']}")
    lines.append(f"labeled by: {st['by_labeler']}; judge suggestions attached: {st['with_suggestion']}")
    lines.append(
        f"gold spans saved: {st['with_gold_span']}; boundary corrected (differs from rules): "
        f"{st['boundary_corrected']} (low/medium: {st['boundary_corrected_low_medium']}) "
        f"/ target {st['targets']['boundary_corrected']}"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="legallm-gold", description="Gold set manifest, verification, and labeling.")
    ap.add_argument("--gold", type=Path, default=DEFAULT_GOLD_PATH, help="gold JSONL path")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="build the manifest from the audit parquet + failures")
    p_init.add_argument("--audit-parquet", type=Path, default=DEFAULT_AUDIT_PARQUET)
    p_init.add_argument("--failures", type=Path, default=DEFAULT_FAILURES_JSONL)
    p_init.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    p_init.add_argument("--n-failures", type=int, default=20)
    p_init.add_argument("--seed", type=int, default=42)
    p_init.add_argument("--force", action="store_true", help="overwrite an existing manifest (labels are lost)")
    p_init.add_argument("--no-verify", action="store_true", help="skip recomputing doc_text for every PDF")

    sub.add_parser("verify", help="recompute doc_text and check spans / sha for every record")
    sub.add_parser("stats", help="labeling progress")
    p_label = sub.add_parser("label", help="launch the Streamlit labeler")
    p_label.add_argument("--port", type=int, default=8501)
    p_pre = sub.add_parser("prefill", help="attach LLM-judge verdicts as suggestions (labels untouched)")
    p_pre.add_argument("--judge", type=Path, required=True, help="legallm-judge verdicts JSONL")
    p_pre.add_argument("--overwrite", action="store_true", help="replace existing suggestions")
    p_acc = sub.add_parser("accept-judge", help="bulk-accept judge suggestions as labels (labeler=judge:<model>)")
    p_acc.add_argument("--policies", nargs="+", choices=POLICIES, default=["nonbrief"])
    p_acc.add_argument("--min-confidence", choices=["low", "medium", "high"], default="high")
    p_acc.add_argument("--dry-run", action="store_true")

    args = ap.parse_args(argv)

    if args.cmd == "init":
        if args.gold.exists() and not args.force:
            print(
                f"error: {args.gold} exists; pass --force to rebuild (existing labels would be lost)", file=sys.stderr
            )
            return 2
        records = build_manifest(
            args.audit_parquet, args.failures, args.pdf_dir, n_failures=args.n_failures, seed=args.seed
        )
        if not args.no_verify:
            problems = verify_all(records, progress=True)
            for gid, ps in problems.items():
                print(f"  {gid}: {'; '.join(ps)}")
        save_gold(records, args.gold)
        meta = write_meta(args.gold, records, seed=args.seed, n_failures=args.n_failures)
        print(f"wrote {args.gold} ({len(records)} records) + {meta.name}")
        return 0

    records = load_gold(args.gold)
    if args.cmd == "verify":
        problems = verify_all(records, progress=True)
        save_gold(records, args.gold)  # persists any newly filled doc_sha1
        for gid, ps in problems.items():
            print(f"  {gid}: {'; '.join(ps)}")
        print(f"{len(records) - len(problems)}/{len(records)} records OK")
        return 1 if problems else 0
    if args.cmd == "stats":
        print(format_stats(stats(records)))
        return 0
    if args.cmd == "prefill":
        verdicts = load_verdicts(args.judge)
        counts = prefill(records, verdicts, args.judge.stem, overwrite=args.overwrite)
        save_gold(records, args.gold)
        print(f"prefill from {args.judge.name}: {counts}")
        return 0
    if args.cmd == "accept-judge":
        counts = accept_judge(
            records, policies=set(args.policies), min_confidence=args.min_confidence, dry_run=args.dry_run
        )
        if not args.dry_run:
            save_gold(records, args.gold)
        mode = "dry run" if args.dry_run else "applied"
        print(f"accept-judge ({mode}; policies={args.policies}, min_confidence={args.min_confidence}): {counts or {}}")
        print(format_stats(stats(records)))
        return 0
    if args.cmd == "label":
        app = Path(__file__).with_name("labeler_app.py")
        cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app),
            "--server.port",
            str(args.port),
            "--",
            "--gold",
            str(args.gold),
        ]
        print("launching:", " ".join(cmd))
        return subprocess.call(cmd)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
