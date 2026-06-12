"""End-to-end smoke test for the dry-run bridge loop."""

import json
import os
import subprocess
import sys
from pathlib import Path


def run_cli(repo_root: Path, args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    test_env = {**os.environ, "PYTHONPATH": str(repo_root / "src")}
    if env:
        test_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "hermes_beads.cli", *args],
        cwd=repo_root,
        env=test_env,
        capture_output=True,
        text=True,
    )


def test_dry_run_dispatch_and_result_sync_loop(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ready_bead = {
        "id": "hb-smoke",
        "title": "Smoke task",
        "description": "Verify bridge loop without external services",
        "status": "open",
        "priority": 1,
        "issue_type": "task",
        "metadata": {
            "hermes_profile": "ts-dev",
            "hermes_mode": "pr",
            "hermes_stop_condition": "dry-run payload produced",
        },
        "dependencies": [],
        "labels": ["testing"],
    }

    dispatch = run_cli(
        repo_root,
        ["bridge", "dispatch", "--dry-run"],
        env={"HB_MOCK_BD_READY_JSON": json.dumps([ready_bead])},
    )
    assert dispatch.returncode == 0, dispatch.stderr
    dispatch_payload = json.loads(dispatch.stdout)
    assert dispatch_payload["tasks"][0]["source_bead_id"] == "hb-smoke"

    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            [
                {
                    "source_bead_id": "hb-smoke",
                    "status": "completed",
                    "summary": "smoke completed",
                }
            ]
        )
    )
    sync = run_cli(
        repo_root,
        ["bridge", "sync-results", "--dry-run", "--results-file", str(results_file)],
    )
    assert sync.returncode == 0, sync.stderr
    operations = json.loads(sync.stdout)["operations"]
    assert operations == [
        {"op": "comment", "bead_id": "hb-smoke", "body": "result: smoke completed"},
        {"op": "close", "bead_id": "hb-smoke", "reason": "kanban task completed"},
    ]
