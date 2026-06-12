"""End-to-end smoke test for the dry-run bridge loop."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_cli(repo_root: Path, cwd: Path, args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    test_env = {**os.environ, "PYTHONPATH": str(repo_root / "src")}
    if env:
        test_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "hermes_beads.cli", *args],
        cwd=cwd,
        env=test_env,
        capture_output=True,
        text=True,
    )


def run_bd(cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["bd", *args], cwd=cwd, capture_output=True, text=True)


def test_dispatch_and_result_sync_loop_against_temp_beads_workspace(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if subprocess.run(["bd", "version"], capture_output=True).returncode != 0:
        pytest.skip("bd CLI is not installed")

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    init = run_bd(tmp_path, ["init", "--prefix", "sm", "--quiet"])
    assert init.returncode == 0, init.stderr

    created = run_bd(
        tmp_path,
        [
            "create",
            "Smoke task",
            "--description",
            "Verify bridge loop without external services",
            "--type",
            "task",
            "--priority",
            "1",
            "--metadata",
            json.dumps(
                {
                    "hermes_profile": "ts-dev",
                    "hermes_mode": "pr",
                    "hermes_stop_condition": "dry-run payload produced",
                }
            ),
            "--json",
        ],
    )
    assert created.returncode == 0, created.stderr
    bead_id = json.loads(created.stdout)["id"]

    dispatch = run_cli(repo_root, tmp_path, ["bridge", "dispatch", "--dry-run"])
    assert dispatch.returncode == 0, dispatch.stderr
    dispatch_payload = json.loads(dispatch.stdout)
    assert dispatch_payload["tasks"][0]["source_bead_id"] == bead_id

    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            [
                {
                    "source_bead_id": bead_id,
                    "status": "completed",
                    "summary": "smoke completed",
                }
            ]
        )
    )
    sync = run_cli(repo_root, tmp_path, ["bridge", "sync-results", "--apply", "--results-file", str(results_file)])
    assert sync.returncode == 0, sync.stderr
    assert json.loads(sync.stdout)["applied"] is True

    shown = run_bd(tmp_path, ["show", bead_id, "--json"])
    assert shown.returncode == 0, shown.stderr
    bead = json.loads(shown.stdout)[0]
    assert bead["status"] == "closed"

    comments = run_bd(tmp_path, ["comments", bead_id, "--json"])
    assert comments.returncode == 0, comments.stderr
    assert "smoke completed" in comments.stdout


def test_sync_results_apply_idempotent_twice(tmp_path: Path) -> None:
    """Applying the same completed result file twice must not duplicate comments or re-close."""
    repo_root = Path(__file__).resolve().parents[1]
    if subprocess.run(["bd", "version"], capture_output=True).returncode != 0:
        pytest.skip("bd CLI is not installed")

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    init = run_bd(tmp_path, ["init", "--prefix", "idem", "--quiet"])
    assert init.returncode == 0, init.stderr

    created = run_bd(
        tmp_path,
        [
            "create",
            "Idempotency test",
            "--type", "task",
            "--priority", "1",
            "--metadata", json.dumps({"hermes_profile": "ts-dev", "hermes_mode": "pr"}),
            "--json",
        ],
    )
    assert created.returncode == 0, created.stderr
    bead_id = json.loads(created.stdout)["id"]

    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps([
            {
                "source_bead_id": bead_id,
                "status": "completed",
                "summary": "idempotency check",
                "dispatch_id": "task-idem-001",
            }
        ])
    )

    def get_state() -> tuple[str, int]:
        """Return (comments_text, status)."""
        shown = run_bd(tmp_path, ["show", bead_id, "--json"])
        bead = json.loads(shown.stdout)[0]
        comments = run_bd(tmp_path, ["comments", bead_id, "--json"])
        return comments.stdout, bead["status"]

    state1 = get_state()
    sync1 = run_cli(repo_root, tmp_path, ["bridge", "sync-results", "--apply", "--results-file", str(results_file)])
    assert sync1.returncode == 0, sync1.stderr

    state2 = get_state()
    # Apply the same results file a second time
    sync2 = run_cli(repo_root, tmp_path, ["bridge", "sync-results", "--apply", "--results-file", str(results_file)])
    assert sync2.returncode == 0, sync2.stderr

    state3 = get_state()
    # After second apply, state must be unchanged from after first apply
    assert state2 == state3, f"State changed after re-apply: {state2!r} -> {state3!r}"


def test_sync_results_failed_retry_idempotent(tmp_path: Path) -> None:
    """Applying the same failed result twice increments iteration once only."""
    repo_root = Path(__file__).resolve().parents[1]
    if subprocess.run(["bd", "version"], capture_output=True).returncode != 0:
        pytest.skip("bd CLI is not installed")

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    init = run_bd(tmp_path, ["init", "--prefix", "failidem", "--quiet"])
    assert init.returncode == 0, init.stderr

    created = run_bd(
        tmp_path,
        [
            "create", "Failed retry test",
            "--type", "task", "--priority", "1",
            "--metadata", json.dumps({"hermes_profile": "ts-dev", "hermes_mode": "pr"}),
            "--json",
        ],
    )
    assert created.returncode == 0, created.stderr
    bead_id = json.loads(created.stdout)["id"]

    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps([
            {
                "source_bead_id": bead_id,
                "status": "failed",
                "summary": "timeout",
                "dispatch_id": "task-fail-001",
            }
        ])
    )

    def get_iteration() -> int:
        shown = run_bd(tmp_path, ["show", bead_id, "--json"])
        bead = json.loads(shown.stdout)[0]
        return int(bead.get("metadata", {}).get("hermes_iteration", 0) or 0)

    sync1 = run_cli(repo_root, tmp_path, ["bridge", "sync-results", "--apply", "--results-file", str(results_file)])
    assert sync1.returncode == 0, sync1.stderr
    iter1 = get_iteration()
    assert iter1 == 1, f"Expected iteration 1 after first apply, got {iter1}"

    sync2 = run_cli(repo_root, tmp_path, ["bridge", "sync-results", "--apply", "--results-file", str(results_file)])
    assert sync2.returncode == 0, sync2.stderr
    iter2 = get_iteration()
    assert iter2 == iter1, f"Iteration changed after re-apply: {iter1} -> {iter2}"
