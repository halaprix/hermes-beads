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
    (tmp_path / "VERSION").write_text("1.0.0-test\n")
    (src_dir / "__init__.py").write_text("")
    # Copy all .py modules from the package (not just a hardcoded list)
    pkg_src = Path(__file__).parent.parent / "src" / "hermes_beads"
    for module in pkg_src.glob("*.py"):
        (src_dir / module.name).write_text(module.read_text())
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


def init_real_bd_workspace(cwd: Path, prefix: str = "cli") -> None:
    subprocess.run(["git", "init", "-q"], cwd=cwd, check=True)
    result = subprocess.run(
        [
            "bd",
            "init",
            "--prefix",
            prefix,
            "--quiet",
            "--non-interactive",
            "--skip-agents",
            "--skip-hooks",
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def create_ready_bead(cwd: Path, title: str) -> str:
    result = subprocess.run(
        [
            "bd",
            "create",
            title,
            "--metadata",
            json.dumps(
                {
                    "hermes_status": "ready",
                    "hermes_profile": "ts-dev",
                    "hermes_mode": "pr",
                    "hermes_stop_condition": "done means tested",
                }
            ),
            "--json",
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    if isinstance(data, list):
        return data[0]["id"]
    return data["id"]


def show_bead(cwd: Path, bead_id: str) -> dict:
    result = subprocess.run(
        ["bd", "show", bead_id, "--json"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    if isinstance(data, list):
        return data[0]
    return data


def test_version(mock_repo_root: Path) -> None:
    result = run_hb(["--version"], mock_repo_root)
    assert result.returncode == 0
    assert "1.0.0-test" in result.stdout


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


def test_bridge_dispatch_preserves_handoff_comments(mock_repo_root: Path) -> None:
    env = {
        "HB_MOCK_BD_READY_JSON": json.dumps([bead(id="hb-fup", title="Bridge task")]),
        "HB_MOCK_BD_COMMENTS_JSON": json.dumps(
            [
                {
                    "bead_id": "hb-fup",
                    "author": "agent",
                    "body": "handoff: keep context",
                    "created_at": "2026-06-12T12:00:00Z",
                }
            ]
        ),
    }
    result = run_hb(["bridge", "dispatch", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    body = json.loads(data["tasks"][0]["body"])
    assert body["comments"] == [
        {
            "author": "agent",
            "body": "handoff: keep context",
            "created_at": "2026-06-12T12:00:00Z",
        }
    ]


def test_bridge_dispatch_empty_queue_is_success(mock_repo_root: Path) -> None:
    env = {"HB_MOCK_BD_READY_JSON": "[]"}
    result = run_hb(["bridge", "dispatch", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"tasks": []}


def test_bridge_dispatch_apply_local_file_creates_queue_file(mock_repo_root: Path) -> None:
    init_real_bd_workspace(mock_repo_root, prefix="cli")
    bead_id = create_ready_bead(mock_repo_root, "Apply task")
    queue_file = Path(".hermes-beads/dispatch.json")

    result = run_hb(
        [
            "bridge",
            "dispatch",
            "--apply",
            "--backend",
            "local-file",
            "--queue-file",
            str(queue_file),
        ],
        mock_repo_root,
    )

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["applied"] is True
    assert data["backend"] == "local-file"
    assert data["queue_file"].endswith(".hermes-beads/dispatch.json")
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["payload"]["source_bead_id"] == bead_id
    queue_path = mock_repo_root / queue_file
    assert queue_path.exists()
    queue = json.loads(queue_path.read_text())
    assert len(queue["tasks"]) == 1
    assert queue["tasks"][0]["payload"]["source_bead_id"] == bead_id
    linked = show_bead(mock_repo_root, bead_id)
    assert linked["metadata"]["hermes_kanban_task_id"] == data["tasks"][0]["id"]


def test_bridge_dispatch_apply_requires_backend_and_queue_file(mock_repo_root: Path) -> None:
    env = {"HB_MOCK_BD_READY_JSON": json.dumps([bead(id="hb-apply", title="Apply task")])}

    missing_backend = run_hb(
        ["bridge", "dispatch", "--apply", "--queue-file", ".hermes-beads/dispatch.json"],
        mock_repo_root,
        env=env,
    )
    assert missing_backend.returncode == 1
    assert "backend local-file" in missing_backend.stderr.lower()

    missing_queue = run_hb(
        ["bridge", "dispatch", "--apply", "--backend", "local-file"],
        mock_repo_root,
        env=env,
    )
    assert missing_queue.returncode == 1
    assert "queue-file" in missing_queue.stderr.lower()


def test_bridge_dispatch_apply_local_file_is_idempotent(mock_repo_root: Path) -> None:
    init_real_bd_workspace(mock_repo_root, prefix="cli")
    create_ready_bead(mock_repo_root, "Duplicate task")
    queue_file = Path(".hermes-beads/dispatch.json")
    args = [
        "bridge",
        "dispatch",
        "--apply",
        "--backend",
        "local-file",
        "--queue-file",
        str(queue_file),
    ]

    first = run_hb(args, mock_repo_root)
    second = run_hb(args, mock_repo_root)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout)["tasks"] == []
    queue_path = mock_repo_root / queue_file
    queue = json.loads(queue_path.read_text())
    assert len(queue["tasks"]) == 1


def test_bridge_dispatch_apply_marks_bead_not_ready(mock_repo_root: Path) -> None:
    init_real_bd_workspace(mock_repo_root, prefix="cli")
    bead_id = create_ready_bead(mock_repo_root, "Status gate task")
    queue_file = Path(".hermes-beads/dispatch.json")

    result = run_hb(
        [
            "bridge",
            "dispatch",
            "--apply",
            "--backend",
            "local-file",
            "--queue-file",
            str(queue_file),
        ],
        mock_repo_root,
    )

    assert result.returncode == 0, result.stderr
    ready = subprocess.run(
        ["bd", "ready", "--json"],
        cwd=mock_repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ready.returncode == 0, ready.stderr
    ready_data = json.loads(ready.stdout)
    assert bead_id not in {item["id"] for item in ready_data}
    bead = show_bead(mock_repo_root, bead_id)
    assert bead["status"] == "in_progress"


def test_result_sync_success_operations(mock_repo_root: Path, tmp_path: Path) -> None:
    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps([{"bead_id": "hb-xaz", "status": "completed", "summary": "ok"}]))
    result = run_hb(
        ["bridge", "sync-results", "--dry-run", "--results-file", str(results_file)],
        mock_repo_root,
        env={"HB_MOCK_BD_COMMENTS_JSON": "[]"},
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["operations"] == [
        {"op": "comment", "bead_id": "hb-xaz", "body": "hermes-beads-op: hb-xaz-8262b954\nresult: ok"},
        {"op": "close", "bead_id": "hb-xaz", "reason": "kanban task completed"},
    ]


def test_result_sync_failed_increments_iteration(mock_repo_root: Path, tmp_path: Path) -> None:
    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps([{"bead_id": "hb-xaz", "status": "failed", "summary": "timeout"}]))
    env = {
        "HB_MOCK_BD_SHOW_JSON": json.dumps(
            [bead(id="hb-xaz", metadata={"hermes_iteration": 2, "hermes_profile": "ts-dev"})]
        ),
        "HB_MOCK_BD_COMMENTS_JSON": "[]",
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
    data = json.loads(result.stdout)
    assert data["hermes_profile"] == "ts-dev"
    assert data["reason"] == "explicit metadata.hermes_profile"


def test_handoff_resolves_profile_when_metadata_is_absent(mock_repo_root: Path) -> None:
    env = {"HB_MOCK_BD_SHOW_JSON": json.dumps([bead(id="hb-doc", metadata={}, labels=["docs"])])}
    result = run_hb(["handoff", "hb-doc", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    assert json.loads(result.stdout)["hermes_profile"] == "docs"


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


# -----------------------------------------------------------------------
# hb-b88.4: result-sync dry-run marks duplicate operations as skipped
# -----------------------------------------------------------------------

def _make_op_id(bead_id: str, dispatch_id: str, summary: str) -> str:
    """Helper to compute the expected op ID for a completed result."""
    import hashlib
    h = hashlib.sha256(f"{bead_id}\n{dispatch_id}\ncompleted\n{summary}".encode()).hexdigest()[:8]
    return f"{bead_id}-{h}"


def test_result_sync_dry_run_marks_duplicate_as_skipped(mock_repo_root: Path, tmp_path: Path) -> None:
    """When an existing comment already has the op marker, dry-run reports skipped."""
    bead_id = "hb-dup"
    dispatch_id = "task-789"
    summary = "all good"
    op_id = _make_op_id(bead_id, dispatch_id, summary)

    # Simulate prior sync: comment with hermes-beads-op marker already present
    existing_comment = {
        "author": "hermes-beads",
        "body": f"hermes-beads-op: {op_id}\nresult: {summary}",
        "created_at": "2026-06-12T10:00:00Z",
    }

    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps([
        {"bead_id": bead_id, "status": "completed", "summary": summary, "dispatch_id": dispatch_id}
    ]))

    env = {
        "HB_MOCK_BD_SHOW_JSON": json.dumps([bead(id=bead_id)]),
        "HB_MOCK_BD_COMMENTS_JSON": json.dumps([existing_comment]),
    }
    result = run_hb(
        ["bridge", "sync-results", "--dry-run", "--results-file", str(results_file)],
        mock_repo_root,
        env=env,
    )
    assert result.returncode == 0
    ops = json.loads(result.stdout)["operations"]
    # All ops for this bead should be skipped
    assert all(o.get("op") == "skipped" for o in ops)
    assert all(o.get("bead_id") == bead_id for o in ops)


def test_result_sync_dry_run_first_run_no_marker_still_plans_ops(mock_repo_root: Path, tmp_path: Path) -> None:
    """When no prior marker exists, dry-run plans comment+close operations."""
    bead_id = "hb-new"
    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps([
        {"bead_id": bead_id, "status": "completed", "summary": "ok"}
    ]))
    # No existing comments
    env = {
        "HB_MOCK_BD_SHOW_JSON": json.dumps([bead(id=bead_id)]),
        "HB_MOCK_BD_COMMENTS_JSON": json.dumps([]),
    }
    result = run_hb(
        ["bridge", "sync-results", "--dry-run", "--results-file", str(results_file)],
        mock_repo_root,
        env=env,
    )
    assert result.returncode == 0
    ops = json.loads(result.stdout)["operations"]
    op_types = [o["op"] for o in ops]
    assert "comment" in op_types
    assert "close" in op_types


def test_result_sync_dry_run_mixed_beads_one_skipped_one_new(mock_repo_root: Path, tmp_path: Path) -> None:
    """One bead has prior marker (skipped), another is fresh (planned)."""
    bead_old = "hb-old"
    bead_new = "hb-new"
    dispatch_id = "task-111"
    summary = "done"
    op_id = _make_op_id(bead_old, dispatch_id, summary)

    existing_comment = {
        "author": "hermes-beads",
        "body": f"hermes-beads-op: {op_id}",
        "created_at": "2026-06-12T10:00:00Z",
    }

    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps([
        {"bead_id": bead_old, "status": "completed", "summary": summary, "dispatch_id": dispatch_id},
        {"bead_id": bead_new, "status": "completed", "summary": summary, "dispatch_id": dispatch_id},
    ]))

    env = {
        "HB_MOCK_BD_SHOW_JSON": json.dumps([bead(id=bead_old), bead(id=bead_new)]),
        "HB_MOCK_BD_COMMENTS_JSON": json.dumps([existing_comment]),
    }
    result = run_hb(
        ["bridge", "sync-results", "--dry-run", "--results-file", str(results_file)],
        mock_repo_root,
        env=env,
    )
    assert result.returncode == 0
    ops = json.loads(result.stdout)["operations"]
    old_ops = [o for o in ops if o.get("bead_id") == bead_old]
    new_ops = [o for o in ops if o.get("bead_id") == bead_new]
    assert all(o.get("op") == "skipped" for o in old_ops)
    assert all(o.get("op") != "skipped" for o in new_ops)


# -----------------------------------------------------------------------
# hb-b88.7: malformed result records produce skipped diagnostics
# -----------------------------------------------------------------------

def test_result_sync_missing_bead_id_is_skipped(mock_repo_root: Path, tmp_path: Path) -> None:
    """Result record without bead_id/source_bead_id produces skipped diagnostic."""
    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps([{"status": "completed", "summary": "orphan"}]))
    result = run_hb(
        ["bridge", "sync-results", "--dry-run", "--results-file", str(results_file)],
        mock_repo_root,
        env={"HB_MOCK_BD_COMMENTS_JSON": "[]"},
    )
    assert result.returncode == 0
    ops = json.loads(result.stdout)["operations"]
    # Should be marked as skipped with a reason
    assert any(o.get("op") == "skipped" and "bead_id" in o.get("reason", "") for o in ops)


def test_result_sync_unknown_status_is_skipped(mock_repo_root: Path, tmp_path: Path) -> None:
    """Result with unknown status produces skipped diagnostic (no side effects)."""
    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps([
        {"bead_id": "hb-xyz", "status": "unknown_status", "summary": "huh?"}
    ]))
    result = run_hb(
        ["bridge", "sync-results", "--dry-run", "--results-file", str(results_file)],
        mock_repo_root,
        env={"HB_MOCK_BD_COMMENTS_JSON": "[]"},
    )
    assert result.returncode == 0
    ops = json.loads(result.stdout)["operations"]
    skipped = [o for o in ops if o.get("bead_id") == "hb-xyz"]
    # Unknown status -> skipped (not comment, not close, not metadata update)
    assert all(o.get("op") == "skipped" for o in skipped)


def test_result_sync_valid_bead_still_processed(mock_repo_root: Path, tmp_path: Path) -> None:
    """Valid record alongside malformed one is processed normally."""
    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps([
        {"bead_id": "hb-bad", "status": "unknown_status", "summary": "bad"},
        {"bead_id": "hb-good", "status": "completed", "summary": "ok"},
    ]))
    result = run_hb(
        ["bridge", "sync-results", "--dry-run", "--results-file", str(results_file)],
        mock_repo_root,
        env={"HB_MOCK_BD_COMMENTS_JSON": "[]"},
    )
    assert result.returncode == 0
    ops = json.loads(result.stdout)["operations"]
    good_ops = [o for o in ops if o.get("bead_id") == "hb-good"]
    assert any(o.get("op") == "comment" for o in good_ops)
    assert any(o.get("op") == "close" for o in good_ops)
