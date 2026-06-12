"""Tests for hermes-beads CLI."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def mock_repo_root(tmp_path: Path) -> Generator[Path, None, None]:
    """Set up a mock repo with proper directory structure."""
    src_dir = tmp_path / "src" / "hermes_beads"
    src_dir.mkdir(parents=True)
    (tmp_path / "VERSION").write_text("0.2.0-test\n")
    (src_dir / "__init__.py").write_text("")
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


def bead(**overrides: object) -> dict:
    data = {
        "id": "hb-test123",
        "title": "Test task",
        "description": "A test task",
        "status": "open",
        "priority": 1,
        "issue_type": "task",
        "metadata": {
            "hermes_status": "ready",
            "hermes_profile": "ts-dev",
            "hermes_mode": "pr",
            "hermes_stop_condition": "done means tested",
        },
        "dependencies": [],
        "labels": ["cli"],
    }
    data.update(overrides)
    return data


def test_version(mock_repo_root: Path) -> None:
    result = run_hb(["--version"], mock_repo_root)
    assert result.returncode == 0
    assert "0.2.0-test" in result.stdout


def test_ready_dry_run(mock_repo_root: Path) -> None:
    env = {"HB_MOCK_BD_READY_JSON": json.dumps([bead()])}
    result = run_hb(["ready", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["bead_id"] == "hb-test123"
    assert data["stop_condition"] == "done means tested"


def test_handoff_dry_run(mock_repo_root: Path) -> None:
    test_bead = bead(id="hb-as6", title="Add minimal dry-run CLI skeleton")
    env = {"HB_MOCK_BD_SHOW_JSON": json.dumps([test_bead])}
    result = run_hb(["handoff", "hb-as6", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["bead_id"] == "hb-as6"
    assert data["goal"] == "Add minimal dry-run CLI skeleton"


def test_handoff_not_found(mock_repo_root: Path) -> None:
    env = {"HB_MOCK_BD_SHOW_JSON": "[]"}
    result = run_hb(["handoff", "hb-nonexistent", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 1
    assert "not found" in result.stderr.lower()


def test_handoff_includes_comments_when_available(mock_repo_root: Path) -> None:
    env = {
        "HB_MOCK_BD_SHOW_JSON": json.dumps([bead(id="hb-yhl")]),
        "HB_MOCK_BD_COMMENTS_JSON": json.dumps(
            [
                {
                    "author": "agent",
                    "body": "decision: preserve dry-run default",
                    "created_at": "2026-06-12T12:00:00Z",
                }
            ]
        ),
    }
    result = run_hb(["handoff", "hb-yhl", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["comments"] == [
        {
            "author": "agent",
            "body": "decision: preserve dry-run default",
            "created_at": "2026-06-12T12:00:00Z",
        }
    ]


def test_bridge_dispatch_dry_run_maps_ready_beads(mock_repo_root: Path) -> None:
    env = {"HB_MOCK_BD_READY_JSON": json.dumps([bead(id="hb-fup", title="Bridge task")])}
    result = run_hb(["bridge", "dispatch", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data["tasks"]) == 1
    task = data["tasks"][0]
    assert task["source_bead_id"] == "hb-fup"
    assert task["assignee"] == "ts-dev"
    assert json.loads(task["body"])["bead_id"] == "hb-fup"


def test_bridge_dispatch_empty_queue_is_success(mock_repo_root: Path) -> None:
    env = {"HB_MOCK_BD_READY_JSON": "[]"}
    result = run_hb(["bridge", "dispatch", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"tasks": []}


def test_result_sync_success_operations(mock_repo_root: Path, tmp_path: Path) -> None:
    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps([{"bead_id": "hb-xaz", "status": "completed", "summary": "ok"}]))
    result = run_hb(
        ["bridge", "sync-results", "--dry-run", "--results-file", str(results_file)],
        mock_repo_root,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["operations"] == [
        {"op": "comment", "bead_id": "hb-xaz", "body": "result: ok"},
        {"op": "close", "bead_id": "hb-xaz", "reason": "kanban task completed"},
    ]


def test_result_sync_failed_increments_iteration(mock_repo_root: Path, tmp_path: Path) -> None:
    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps([{"bead_id": "hb-xaz", "status": "failed", "summary": "timeout"}]))
    env = {
        "HB_MOCK_BD_SHOW_JSON": json.dumps(
            [bead(id="hb-xaz", metadata={"hermes_iteration": 2, "hermes_profile": "ts-dev"})]
        )
    }
    result = run_hb(
        ["bridge", "sync-results", "--dry-run", "--results-file", str(results_file)],
        mock_repo_root,
        env=env,
    )
    assert result.returncode == 0
    operations = json.loads(result.stdout)["operations"]
    assert operations[-1] == {
        "op": "update-metadata",
        "bead_id": "hb-xaz",
        "metadata": {"hermes_status": "failed", "hermes_iteration": 3},
    }


def test_gate_profile_uses_explicit_profile(mock_repo_root: Path) -> None:
    env = {"HB_MOCK_BD_SHOW_JSON": json.dumps([bead(id="hb-zjv")])}
    result = run_hb(["bridge", "profile", "hb-zjv", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    assert json.loads(result.stdout)["hermes_profile"] == "ts-dev"


def test_gate_profile_defaults_for_docs_label(mock_repo_root: Path) -> None:
    env = {
        "HB_MOCK_BD_SHOW_JSON": json.dumps(
            [bead(id="hb-a6n", metadata={}, labels=["docs", "architecture"])]
        )
    }
    result = run_hb(["bridge", "profile", "hb-a6n", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    assert json.loads(result.stdout)["hermes_profile"] == "docs"


def test_gate_profile_defaults_architecture_to_planner(mock_repo_root: Path) -> None:
    env = {
        "HB_MOCK_BD_SHOW_JSON": json.dumps(
            [bead(id="hb-a6n", metadata={}, labels=["architecture"])]
        )
    }
    result = run_hb(["bridge", "profile", "hb-a6n", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    assert json.loads(result.stdout)["hermes_profile"] == "planner"
