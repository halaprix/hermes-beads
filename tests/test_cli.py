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


def install_fake_hermes(tmp_path: Path, fail_create: bool = False) -> tuple[Path, Path]:
    """Install a fake `hermes` executable that records argv to a log file."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_file = tmp_path / "fake-hermes.log"
    script = bin_dir / "hermes"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "import json",
                "import os",
                "import sys",
                "from pathlib import Path",
                "",
                "log = Path(os.environ['FAKE_HERMES_LOG'])",
                "log.parent.mkdir(parents=True, exist_ok=True)",
                "with log.open('a', encoding='utf-8') as fh:",
                "    fh.write(json.dumps(sys.argv[1:]) + '\\\\n')",
                "",
                "args = sys.argv[1:]",
                "if len(args) < 2 or args[0] != 'kanban':",
                "    print('unexpected command', file=sys.stderr)",
                "    sys.exit(2)",
                "",
                "if args[1] == 'create':",
                "    if os.environ.get('FAKE_HERMES_CREATE_FAIL') == '1':",
                "        print('create failed before mutation', file=sys.stderr)",
                "        sys.exit(1)",
                "    print(json.dumps({'id': 'task-123', 'status': 'running'}))",
                "    sys.exit(0)",
                "",
                "if args[1] == 'show':",
                "    if os.environ.get('FAKE_HERMES_SHOW_FAIL') == '1':",
                "        print('show failed after mutation', file=sys.stderr)",
                "        sys.exit(1)",
                "    task_id = args[2] if len(args) > 2 else ''",
                "    if task_id == 'task-123':",
                "        print(json.dumps({'id': task_id, 'status': 'running'}))",
                "    sys.exit(0)",
                "",
                "if args[1] == 'complete':",
                "    print(json.dumps({'id': args[2], 'status': 'completed'}))",
                "    sys.exit(0)",
                "",
                "print('unsupported subcommand', file=sys.stderr)",
                "sys.exit(2)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bin_dir, log_file


def read_fake_hermes_log(log_file: Path) -> list[list[str]]:
    """Decode the fake Hermes argv log written as concatenated JSON arrays."""
    text = log_file.read_text().strip()
    if not text:
        return []
    decoder = json.JSONDecoder()
    entries: list[list[str]] = []
    index = 0
    while index < len(text):
        while index < len(text) and text[index] in " \t\r\n":
            index += 1
        if index >= len(text):
            break
        entry, end = decoder.raw_decode(text, index)
        entries.append(entry)
        index = end
        while index < len(text) and text[index] in " \t\r\n":
            index += 1
        if text.startswith("\\n", index):
            index += 2
    return entries


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
    assert "choose a dispatch backend" in missing_backend.stderr.lower()

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


def test_bridge_tick_apply_local_file_repeated_has_no_duplicates(mock_repo_root: Path) -> None:
    init_real_bd_workspace(mock_repo_root, prefix="cli")
    bead_id = create_ready_bead(mock_repo_root, "Tick local task")
    queue_file = Path(".hermes-beads/tick-dispatch.json")

    first = run_hb(
        ["bridge", "tick", "--apply", "--backend", "local-file", "--queue-file", str(queue_file)],
        mock_repo_root,
    )
    second = run_hb(
        ["bridge", "tick", "--apply", "--backend", "local-file", "--queue-file", str(queue_file)],
        mock_repo_root,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert json.loads(first.stdout)["summary"]["dispatch_count"] == 1
    assert json.loads(second.stdout)["summary"]["dispatch_count"] == 0
    queue = json.loads((mock_repo_root / queue_file).read_text(encoding="utf-8"))
    assert len(queue["tasks"]) == 1
    assert show_bead(mock_repo_root, bead_id)["status"] == "in_progress"


def test_bridge_dispatch_apply_hermes_cli_backend_writes_link_after_success(mock_repo_root: Path) -> None:
    init_real_bd_workspace(mock_repo_root, prefix="cli")
    bead_id = create_ready_bead(mock_repo_root, "Hermes CLI backend task")
    bead_before = show_bead(mock_repo_root, bead_id)
    bin_dir, log_file = install_fake_hermes(mock_repo_root)
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_HERMES_LOG": str(log_file),
    }

    result = run_hb(
        [
            "bridge",
            "dispatch",
            "--apply",
            "--backend",
            "hermes-cli",
        ],
        mock_repo_root,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["backend"] == "hermes-cli"
    assert payload["applied"] is True
    assert len(payload["tasks"]) == 1
    assert payload["tasks"][0]["id"] == "task-123"
    assert payload["tasks"][0]["status"] == "running"
    log_entries = read_fake_hermes_log(log_file)
    assert log_entries[0][0:4] == ["kanban", "create", f"{bead_id}: Hermes CLI backend task", "--body"]
    assert "--idempotency-key" in log_entries[0]
    assert log_entries[0][log_entries[0].index("--idempotency-key") + 1] == bead_id
    assert log_entries[0][-1] == "--json"
    body = json.loads(log_entries[0][log_entries[0].index("--body") + 1])
    assert body["bead_id"] == bead_id
    assert log_entries[1] == ["kanban", "show", "task-123", "--json"]
    bead_after = show_bead(mock_repo_root, bead_id)
    assert bead_after["metadata"]["hermes_kanban_task_id"] == "task-123"
    assert bead_after["status"] == "in_progress"
    assert bead_before["metadata"].get("hermes_kanban_task_id") is None


def test_bridge_dispatch_apply_hermes_cli_failure_leaves_bead_metadata_unchanged(mock_repo_root: Path) -> None:
    init_real_bd_workspace(mock_repo_root, prefix="cli")
    bead_id = create_ready_bead(mock_repo_root, "Hermes CLI failure task")
    bead_before = show_bead(mock_repo_root, bead_id)
    bin_dir, log_file = install_fake_hermes(mock_repo_root, fail_create=True)
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_HERMES_LOG": str(log_file),
        "FAKE_HERMES_CREATE_FAIL": "1",
    }

    result = run_hb(
        [
            "bridge",
            "dispatch",
            "--apply",
            "--backend",
            "hermes-cli",
        ],
        mock_repo_root,
        env=env,
    )

    assert result.returncode == 1
    assert "create failed before mutation" in result.stderr
    log_entries = read_fake_hermes_log(log_file)
    assert log_entries[0][0:4] == ["kanban", "create", f"{bead_id}: Hermes CLI failure task", "--body"]
    assert log_entries[0][-1] == "--json"
    bead_after = show_bead(mock_repo_root, bead_id)
    assert bead_after["metadata"] == bead_before["metadata"]
    assert bead_after["status"] == bead_before["status"]


def test_bridge_dispatch_apply_hermes_cli_show_failure_does_not_fail_after_mutation(mock_repo_root: Path) -> None:
    init_real_bd_workspace(mock_repo_root, prefix="cli")
    bead_id = create_ready_bead(mock_repo_root, "Hermes CLI show failure task")
    bin_dir, log_file = install_fake_hermes(mock_repo_root)
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_HERMES_LOG": str(log_file),
        "FAKE_HERMES_SHOW_FAIL": "1",
    }

    result = run_hb(
        [
            "bridge",
            "dispatch",
            "--apply",
            "--backend",
            "hermes-cli",
        ],
        mock_repo_root,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["tasks"] == [{"id": "task-123"}]
    log_entries = read_fake_hermes_log(log_file)
    assert log_entries[0][0:2] == ["kanban", "create"]
    assert log_entries[1] == ["kanban", "show", "task-123", "--json"]
    bead_after = show_bead(mock_repo_root, bead_id)
    assert bead_after["metadata"]["hermes_kanban_task_id"] == "task-123"
    assert bead_after["status"] == "in_progress"


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
        "metadata": {
            "hermes_status": "failed",
            "hermes_iteration": 3,
            "hermes_gate_status": "pending",
            "hermes_gate_type": "retry-escalation",
            "hermes_requires_approval": "true",
            "hermes_gate_reason": "retry threshold reached: 3",
        },
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


def test_gate_profile_routes_review_label_to_reviewer(mock_repo_root: Path) -> None:
    env = {"HB_MOCK_BD_SHOW_JSON": json.dumps([bead(id="hb-rev", metadata={}, labels=["pr-gated"])])}
    result = run_hb(["bridge", "profile", "hb-rev", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["hermes_profile"] == "reviewer"
    assert data["reason"] == "review gate requested"


def test_gates_list_dry_run(mock_repo_root: Path) -> None:
    env = {
        "HB_MOCK_BD_READY_JSON": json.dumps(
            [
                bead(
                    id="hb-gate",
                    metadata={
                        "hermes_requires_approval": "true",
                        "hermes_gate_status": "pending",
                        "hermes_gate_type": "human-approval",
                    },
                )
            ]
        )
    }
    result = run_hb(["gates", "list", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    assert json.loads(result.stdout)["gates"][0]["bead_id"] == "hb-gate"


def test_gates_approve_dry_run(mock_repo_root: Path) -> None:
    env = {
        "HB_MOCK_BD_SHOW_JSON": json.dumps(
            [bead(id="hb-gate", metadata={"hermes_gate_status": "pending"})]
        )
    }
    result = run_hb(["gates", "approve", "hb-gate", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    assert json.loads(result.stdout)["operation"]["op"] == "approve-gate"


def test_dashboard_build_dry_run(mock_repo_root: Path, tmp_path: Path) -> None:
    env = {"HB_MOCK_BD_READY_JSON": json.dumps([bead(id="hb-dash", metadata={})])}
    result = run_hb(["dashboard", "build", "--dry-run", "--output", str(tmp_path / "dash.html")], mock_repo_root, env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["summary"]["total"] == 1


def test_tick_dry_run_noop_silent(mock_repo_root: Path) -> None:
    env = {"HB_MOCK_BD_READY_JSON": "[]"}
    result = run_hb(["bridge", "tick", "--dry-run", "--silent-noop"], mock_repo_root, env=env)
    assert result.returncode == 0
    assert result.stdout == ""


def test_tick_dry_run_filters_gated_beads(mock_repo_root: Path) -> None:
    env = {
        "HB_MOCK_BD_READY_JSON": json.dumps(
            [
                bead(
                    id="hb-gated",
                    metadata={"hermes_requires_approval": "true", "hermes_gate_status": "pending"},
                ),
                bead(id="hb-free", metadata={}),
            ]
        )
    }
    result = run_hb(["bridge", "tick", "--dry-run"], mock_repo_root, env=env)
    assert result.returncode == 0
    assert json.loads(result.stdout)["summary"]["dispatch_count"] == 1


def test_tick_apply_plans_after_bd_pull(mock_repo_root: Path, tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "bd.log"
    pulled = tmp_path / "pulled"
    bd = fake_bin / "bd"
    bd.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "import json, os, sys",
                "from pathlib import Path",
                "log = Path(os.environ['FAKE_BD_LOG'])",
                "pulled = Path(os.environ['FAKE_BD_PULLED'])",
                "args = sys.argv[1:]",
                "log.write_text(log.read_text() + json.dumps(args) + '\\n' if log.exists() else json.dumps(args) + '\\n')",
                "if args == ['--version']:",
                "    print('bd 1.0.0')",
                "elif args == ['dolt', 'pull']:",
                "    pulled.write_text('1')",
                "elif args == ['ready', '--json']:",
                "    ready = [] if not pulled.exists() else [json.loads(os.environ['FAKE_BD_READY_BEAD'])]",
                "    print(json.dumps(ready))",
                "elif args and args[0] == 'comments':",
                "    print('[]')",
                "elif args and args[0] == 'update':",
                "    pass",
                "else:",
                "    print('unexpected bd ' + ' '.join(args), file=sys.stderr)",
                "    sys.exit(2)",
            ]
        ),
        encoding="utf-8",
    )
    bd.chmod(0o755)
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_BD_LOG": str(log),
        "FAKE_BD_PULLED": str(pulled),
        "FAKE_BD_READY_BEAD": json.dumps(bead(id="hb-after-pull", metadata={})),
    }
    result = run_hb(
        ["bridge", "tick", "--apply", "--backend", "local-file", "--bd-pull", "--queue-file", "queue.json"],
        mock_repo_root,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["summary"]["dispatch_count"] == 1
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert calls.index(["dolt", "pull"]) < calls.index(["ready", "--json"])


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
