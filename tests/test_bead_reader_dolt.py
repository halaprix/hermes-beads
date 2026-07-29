"""Tests for reading a Dolt-backed Beads workspace via the bd CLI.

Current Beads stores issues in Dolt and does not write ``.beads/issues.jsonl``
unless the workspace opts in to ``export.auto``. These tests cover the CLI
fallback that keeps such workspaces readable, and assert the on-disk JSONL
fast path still wins when the file is present.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hermes_beads.bead_reader import discover_projects, read_project_beads


def _bd_installed() -> bool:
    try:
        return subprocess.run(["bd", "version"], capture_output=True, text=True).returncode == 0
    except FileNotFoundError:
        return False


pytestmark = pytest.mark.skipif(not _bd_installed(), reason="bd CLI is not installed")


def _init_workspace(path: Path, prefix: str) -> Path:
    """Initialise a git + Beads workspace with no JSONL export configured."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(
        ["bd", "init", "--prefix", prefix, "--quiet", "--non-interactive",
         "--skip-agents", "--skip-hooks"],
        cwd=path, capture_output=True, text=True, check=True,
    )
    return path


def _create(path: Path, title: str) -> str:
    result = subprocess.run(
        ["bd", "create", title, "--json"],
        cwd=path, capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    return (data[0] if isinstance(data, list) else data)["id"]


# ═══════════════════════════════════════════════════════════════════════
#  Reading a Dolt-only workspace
# ═══════════════════════════════════════════════════════════════════════


class TestDoltWorkspaceRead:

    def test_reads_beads_without_issues_jsonl(self, tmp_path: Path):
        ws = _init_workspace(tmp_path / "proj", "dolt")
        created = _create(ws, "First bead")

        assert not (ws / ".beads" / "issues.jsonl").exists(), (
            "fixture must exercise the CLI path, not the file path"
        )
        beads = read_project_beads(ws)
        assert [b.id for b in beads] == [created]
        assert beads[0].title == "First bead"

    def test_project_name_is_populated(self, tmp_path: Path):
        ws = _init_workspace(tmp_path / "named-proj", "np")
        _create(ws, "Bead")
        assert read_project_beads(ws)[0].project == "named-proj"

    def test_dependencies_survive_the_cli_round_trip(self, tmp_path: Path):
        ws = _init_workspace(tmp_path / "proj", "dep")
        first = _create(ws, "Blocker")
        second = _create(ws, "Blocked")
        subprocess.run(["bd", "dep", "add", second, first], cwd=ws,
                       capture_output=True, text=True, check=True)

        blocked = next(b for b in read_project_beads(ws) if b.id == second)
        assert first in blocked.blockers

    def test_memories_are_not_returned(self, tmp_path: Path):
        """Memories can hold sensitive agent context — they must never be beads."""
        ws = _init_workspace(tmp_path / "proj", "mem")
        _create(ws, "Real bead")
        subprocess.run(["bd", "remember", "--key", "secret-note", "sensitive content"],
                       cwd=ws, capture_output=True, text=True, check=False)

        beads = read_project_beads(ws)
        assert all("sensitive content" not in (b.title + b.description) for b in beads)


# ═══════════════════════════════════════════════════════════════════════
#  Fast path and failure modes
# ═══════════════════════════════════════════════════════════════════════


class TestReadPathSelection:

    def test_on_disk_jsonl_takes_precedence(self, tmp_path: Path):
        """A present issues.jsonl must be used verbatim — no subprocess."""
        ws = _init_workspace(tmp_path / "proj", "fast")
        _create(ws, "Bead from Dolt")
        (ws / ".beads" / "issues.jsonl").write_text(
            json.dumps({"id": "from-file-1", "title": "Bead from file", "status": "open"}) + "\n",
            encoding="utf-8",
        )
        assert [b.id for b in read_project_beads(ws)] == ["from-file-1"]

    def test_directory_without_beads_returns_empty(self, tmp_path: Path):
        assert read_project_beads(tmp_path) == []

    def test_unreadable_workspace_returns_empty_not_raises(self, tmp_path: Path):
        """A .beads dir that is not a real workspace must degrade, not explode."""
        (tmp_path / ".beads").mkdir()
        assert read_project_beads(tmp_path) == []


# ═══════════════════════════════════════════════════════════════════════
#  Discovery
# ═══════════════════════════════════════════════════════════════════════


class TestDiscovery:

    def test_dolt_workspace_is_discovered(self, tmp_path: Path, monkeypatch):
        root = tmp_path / "root"
        ws = _init_workspace(root / "my-project", "disc")
        _create(ws, "Bead")
        monkeypatch.setenv("HERMES_BEADS_PROJECT_DIRS", str(root))

        found = {p.name: p for p in discover_projects()}
        assert "my-project" in found
        assert found["my-project"].bead_count == 1
