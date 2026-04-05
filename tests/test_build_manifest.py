"""Tests for legallm.build_manifest module."""

import json

from legallm.build_manifest import (
    BuildManifest,
    create_manifest,
    finalize_manifest,
    generate_build_id,
    read_manifest,
    write_manifest,
)


class TestGenerateBuildId:
    def test_returns_string(self):
        bid = generate_build_id({"query": "test"})
        assert isinstance(bid, str)
        assert len(bid) == 12

    def test_hex_characters(self):
        bid = generate_build_id({"query": "test"})
        assert all(c in "0123456789abcdef" for c in bid)

    def test_different_params_different_id(self):
        id1 = generate_build_id({"query": "test1"})
        id2 = generate_build_id({"query": "test2"})
        # Different params should (almost certainly) produce different IDs
        # Not guaranteed but overwhelmingly likely with SHA256
        assert id1 != id2


class TestCreateManifest:
    def test_creates_manifest(self):
        manifest = create_manifest({"query": "merits brief", "max_docs": 100})
        assert isinstance(manifest, BuildManifest)
        assert len(manifest.build_id) == 12
        assert manifest.timestamp_utc is not None
        assert manifest.legallm_version == "0.1.0"
        assert manifest.python_version is not None
        assert manifest.platform is not None
        assert manifest.parameters["query"] == "merits brief"
        assert manifest.parameters["max_docs"] == 100

    def test_dependency_versions_collected(self):
        manifest = create_manifest({})
        assert "pandas" in manifest.dependency_versions
        assert "pypdf" in manifest.dependency_versions
        assert "requests" in manifest.dependency_versions

    def test_git_fields_present(self):
        manifest = create_manifest({})
        # git_commit may be None if not in a git repo, but field should exist
        assert hasattr(manifest, "git_commit")
        assert hasattr(manifest, "git_dirty")


class TestFinalizeManifest:
    def test_adds_results(self):
        manifest = create_manifest({})
        results = {"extracted_spans": 42, "failures": 3}
        finalize_manifest(manifest, results)
        assert manifest.results_summary["extracted_spans"] == 42
        assert manifest.results_summary["failures"] == 3


class TestWriteReadManifest:
    def test_round_trip(self, tmp_path):
        manifest = create_manifest({"query": "test"})
        manifest.results_summary = {"rows": 10}

        path = tmp_path / "manifest.json"
        write_manifest(manifest, path)
        assert path.exists()

        # Verify JSON is valid
        data = json.loads(path.read_text())
        assert data["build_id"] == manifest.build_id
        assert data["parameters"]["query"] == "test"
        assert data["results_summary"]["rows"] == 10

    def test_read_manifest(self, tmp_path):
        manifest = create_manifest({"query": "test"})
        path = tmp_path / "manifest.json"
        write_manifest(manifest, path)

        loaded = read_manifest(path)
        assert loaded.build_id == manifest.build_id
        assert loaded.parameters == manifest.parameters

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "manifest.json"
        manifest = create_manifest({})
        write_manifest(manifest, path)
        assert path.exists()
