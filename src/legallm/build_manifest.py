"""Build manifest generation for reproducible dataset builds.

Produces a build_manifest.json capturing versions, parameters, commit hash,
and timestamps so that any dataset artifact can be traced back to the exact
code and configuration that produced it.

Reference: approved_spec_package_v0_2.md §Reproducibility requirements
"""

from __future__ import annotations

import datetime
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import legallm

# ---------------------------------------------------------------------------
# Build ID generation
# ---------------------------------------------------------------------------


def _git_commit_hash() -> str | None:
    """Get the current git commit hash, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _git_is_dirty() -> bool | None:
    """Check if the working tree has uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return bool(result.stdout.strip())
    except Exception:
        pass
    return None


def generate_build_id(params: dict[str, Any]) -> str:
    """Generate a deterministic build_id from parameters + timestamp.

    The build_id is a short hash of (git_commit, params, timestamp) to
    uniquely identify a build run while remaining human-readable.
    """
    commit = _git_commit_hash() or "unknown"
    ts = datetime.datetime.now(datetime.UTC).isoformat()
    payload = json.dumps({"commit": commit, "params": params, "ts": ts}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Manifest dataclass
# ---------------------------------------------------------------------------


@dataclass
class BuildManifest:
    """Captures all metadata needed to reproduce a dataset build."""

    build_id: str
    timestamp_utc: str
    git_commit: str | None
    git_dirty: bool | None
    legallm_version: str
    python_version: str
    platform: str
    parameters: dict[str, Any] = field(default_factory=dict)
    dependency_versions: dict[str, str] = field(default_factory=dict)
    results_summary: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Dependency version collection
# ---------------------------------------------------------------------------


def _get_dependency_versions() -> dict[str, str]:
    """Collect versions of key dependencies."""
    versions: dict[str, str] = {}

    try:
        import pandas

        versions["pandas"] = pandas.__version__
    except Exception:
        versions["pandas"] = "not installed"

    try:
        import pypdf

        versions["pypdf"] = pypdf.__version__
    except Exception:
        versions["pypdf"] = "not installed"

    try:
        import fitz

        versions["PyMuPDF"] = fitz.version[0] if hasattr(fitz, "version") else "unknown"
    except Exception:
        versions["PyMuPDF"] = "not installed"

    try:
        import requests

        versions["requests"] = requests.__version__
    except Exception:
        versions["requests"] = "not installed"

    return versions


# ---------------------------------------------------------------------------
# Manifest creation and I/O
# ---------------------------------------------------------------------------


def create_manifest(parameters: dict[str, Any]) -> BuildManifest:
    """Create a new build manifest with current environment info."""
    build_id = generate_build_id(parameters)
    return BuildManifest(
        build_id=build_id,
        timestamp_utc=datetime.datetime.now(datetime.UTC).isoformat(),
        git_commit=_git_commit_hash(),
        git_dirty=_git_is_dirty(),
        legallm_version=legallm.__version__,
        python_version=sys.version,
        platform=platform.platform(),
        parameters=parameters,
        dependency_versions=_get_dependency_versions(),
    )


def finalize_manifest(manifest: BuildManifest, results: dict[str, Any]) -> BuildManifest:
    """Add results summary to a manifest after the build completes."""
    manifest.results_summary = results
    return manifest


def write_manifest(manifest: BuildManifest, path: str | Path) -> Path:
    """Write the manifest to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
    return path


def read_manifest(path: str | Path) -> BuildManifest:
    """Read a manifest from a JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return BuildManifest(**data)
