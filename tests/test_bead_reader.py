"""Tests for project discovery configuration.

Tests that ``_load_scan_roots`` resolves scan roots correctly via the
HERMES_BEADS_PROJECT_DIRS env var, and that ``discover_projects``
discovers projects from the resolved roots.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hermes_beads.bead_reader import discover_projects, _load_scan_roots


# ═══════════════════════════════════════════════════════════════════════
#  _load_scan_roots — env var path
# ═══════════════════════════════════════════════════════════════════════


class TestLoadScanRootsEnvVar:
    """Env var is the highest-priority path and works in any test env."""

    def test_single_path(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("HERMES_BEADS_PROJECT_DIRS", str(tmp_path))
        (tmp_path / ".beads").mkdir()
        (tmp_path / ".beads" / "issues.jsonl").touch()

        roots = _load_scan_roots()
        assert roots == [tmp_path]

    def test_multiple_colon_separated(self, tmp_path: Path, monkeypatch):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        monkeypatch.setenv("HERMES_BEADS_PROJECT_DIRS", f"{dir_a}:{dir_b}")

        roots = _load_scan_roots()
        assert roots == [dir_a, dir_b]

    def test_skips_nonexistent(self, tmp_path: Path, monkeypatch):
        real = tmp_path / "real"
        fake = tmp_path / "nonexistent"
        real.mkdir()

        monkeypatch.setenv("HERMES_BEADS_PROJECT_DIRS", f"{real}:{fake}")

        roots = _load_scan_roots()
        assert roots == [real]

    def test_skips_empty_entries(self, tmp_path: Path, monkeypatch):
        real = tmp_path / "real"
        real.mkdir()

        monkeypatch.setenv("HERMES_BEADS_PROJECT_DIRS", f"{real}:")

        roots = _load_scan_roots()
        assert roots == [real]

    def test_tilde_expansion(self, monkeypatch):
        """Verify that ~/ paths are expanded (runs against real filesystem)."""
        ws = Path.home() / "workspace"
        monkeypatch.setenv("HERMES_BEADS_PROJECT_DIRS", "~/workspace")

        roots = _load_scan_roots()
        if ws.is_dir():
            assert ws in roots
        # If ~/workspace doesn't exist, roots is empty — that's fine

    def test_empty_env_falls_to_default(self, monkeypatch):
        """Empty env var defers to config file / default (integration test)."""
        monkeypatch.delenv("HERMES_BEADS_PROJECT_DIRS", raising=False)
        # Just verify it doesn't crash — the actual default depends on the
        # test machine's filesystem.
        roots = _load_scan_roots()
        assert isinstance(roots, list)


# ═══════════════════════════════════════════════════════════════════════
#  discover_projects with explicit scan_roots (bypasses config resolution)
# ═══════════════════════════════════════════════════════════════════════


class TestDiscoverProjectsExplicit:
    """Tests for discover_projects when scan_roots is passed explicitly."""

    def test_discovers_direct_project(self, tmp_path: Path):
        proj = tmp_path / "my-project"
        proj.mkdir()
        (proj / ".beads").mkdir()
        (proj / ".beads" / "issues.jsonl").write_text(
            json.dumps({"id": "bead-1", "title": "Test bead"}) + "\n"
        )

        result = discover_projects(scan_roots=[tmp_path])
        assert len(result) == 1
        assert result[0].name == "my-project"
        assert result[0].bead_count == 1

    def test_discovers_iterdir_projects(self, tmp_path: Path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        for name in ("alpha", "beta"):
            proj = ws / name
            proj.mkdir()
            (proj / ".beads").mkdir()
            (proj / ".beads" / "issues.jsonl").write_text(
                json.dumps({"id": f"{name}-1", "title": f"Bead in {name}"}) + "\n"
            )

        result = discover_projects(scan_roots=[ws])
        assert len(result) == 2
        names = {p.name for p in result}
        assert names == {"alpha", "beta"}

    def test_skips_directories_without_beads(self, tmp_path: Path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "regular-folder").mkdir()
        (ws / "not-a-beads-project").mkdir()

        result = discover_projects(scan_roots=[ws])
        assert len(result) == 0

    def test_empty_scan_roots(self):
        result = discover_projects(scan_roots=[])
        assert result == []


# ═══════════════════════════════════════════════════════════════════════
#  Integration: env var → discover_projects
# ═══════════════════════════════════════════════════════════════════════


class TestDiscoverProjectsIntegration:
    """End-to-end: env var flows through to discovery."""

    def test_env_var_discovers_project(self, tmp_path: Path, monkeypatch):
        proj = tmp_path / "env-project"
        proj.mkdir()
        (proj / ".beads").mkdir()
        (proj / ".beads" / "issues.jsonl").write_text(
            json.dumps({"id": "b1", "title": "From env"}) + "\n"
        )

        monkeypatch.setenv("HERMES_BEADS_PROJECT_DIRS", str(tmp_path))

        result = discover_projects()
        assert len(result) >= 1
        names = [p.name for p in result]
        assert "env-project" in names
