"""Tests for hermes-beads CLI."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_repo_root(tmp_path: Path) -> Generator[Path, None, None]:
    """Set up a mock repo with proper directory structure."""
    # Create src/hermes_beads structure
    src_dir = tmp_path / "src" / "hermes_beads"
    src_dir.mkdir(parents=True)

    # Create VERSION file at repo root
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.1.0-test\n")

    # Create empty __init__.py
    (src_dir / "__init__.py").write_text("")

    # Copy cli.py to the temp location
    cli_source = Path(__file__).parent.parent / "src" / "hermes_beads" / "cli.py"
    (src_dir / "cli.py").write_text(cli_source.read_text())

    yield tmp_path


def run_hb(args: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run the hb CLI command with proper environment."""
    pythonpath = str(cwd / "src")
    test_env = {**os.environ, "PYTHONPATH": pythonpath}
    if env:
        test_env.update(env)

    return subprocess.run(
        [sys.executable, "-m", "hermes_beads.cli"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=test_env,
    )


def test_version(mock_repo_root: Path) -> None:
    """Test hb --version outputs version and exits 0."""
    result = run_hb(["--version"], mock_repo_root)
    assert result.returncode == 0
    assert "0.1.0-test" in result.stdout


def test_ready_dry_run(mock_repo_root: Path) -> None:
    """Test hb ready --dry-run exits 0 and outputs valid JSON with bead_id."""
    # Mock bd ready --json via environment
    test_bead = {
        "id": "hb-test123",
        "title": "Test task",
        "description": "A test task",
        "status": "open",
        "metadata": {
            "hermes_status": "ready",
            "hermes_profile": "ts-dev",
            "hermes_mode": "pr",
        },
        "dependencies": [],
    }

    env = {
        "HB_MOCK_BD_READY_JSON": json.dumps([test_bead]),
    }

    result = run_hb(["ready", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "bead_id" in data
    assert data["bead_id"] == "hb-test123"


def test_handoff_dry_run(mock_repo_root: Path) -> None:
    """Test hb handoff <id> --dry-run exits 0 and outputs valid JSON."""
    test_bead = {
        "id": "hb-as6",
        "title": "Add minimal dry-run CLI skeleton",
        "description": "Create a Python CLI",
        "status": "in_progress",
        "metadata": {
            "hermes_status": "in_progress",
            "hermes_profile": "ts-dev",
            "hermes_mode": "pr",
        },
        "dependencies": [],
    }

    env = {
        "HB_MOCK_BD_SHOW_JSON": json.dumps([test_bead]),
    }

    result = run_hb(["handoff", "hb-as6", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["bead_id"] == "hb-as6"
    assert data["goal"] == "Add minimal dry-run CLI skeleton"


def test_handoff_not_found(mock_repo_root: Path) -> None:
    """Test hb handoff <nonexistent> --dry-run exits 1."""
    env = {
        "HB_MOCK_BD_SHOW_JSON": "[]",
    }

    result = run_hb(["handoff", "hb-nonexistent", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 1
    assert "not found" in result.stderr.lower()
