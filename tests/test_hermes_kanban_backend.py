from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hermes_beads.hermes_kanban_backend import HermesKanbanBackend, HermesKanbanBackendError


def _install_fake_hermes(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_file = tmp_path / "hermes-argv.jsonl"
    script = bin_dir / "hermes"
    script.write_text(
        """#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

log = Path(os.environ['FAKE_HERMES_LOG'])
log.parent.mkdir(parents=True, exist_ok=True)
with log.open('a', encoding='utf-8') as fh:
    fh.write(json.dumps(sys.argv[1:]) + '\\n')

args = sys.argv[1:]
if len(args) < 2 or args[0] != 'kanban':
    print('unexpected invocation', file=sys.stderr)
    sys.exit(2)

cmd = args[1]
if cmd == 'create':
    if os.environ.get('FAKE_HERMES_CREATE_FAIL') == '1':
        print('create failed before mutation', file=sys.stderr)
        sys.exit(1)
    title = args[2]
    print(json.dumps({'id': 'task-123', 'title': title}))
elif cmd == 'show':
    task_id = args[2]
    if task_id == 'missing' or os.environ.get('FAKE_HERMES_SHOW_MISSING') == task_id:
        print(f'no such task: {task_id}', file=sys.stderr)
        sys.exit(0)
    print(json.dumps({'task': {'id': task_id, 'status': 'running', 'title': 'from fake hermes'}}))
elif cmd == 'complete':
    task_id = args[2]
    print(f'Completed {task_id}')
else:
    print(f'unhandled command: {cmd}', file=sys.stderr)
    sys.exit(2)
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bin_dir, log_file


def _read_log(log_file: Path) -> list[list[str]]:
    if not log_file.exists():
        return []
    return [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_create_constructs_kanban_command_and_parses_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir, log_file = _install_fake_hermes(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_HERMES_LOG", str(log_file))

    backend = HermesKanbanBackend()
    task_id = backend.create(
        {
            "title": "Spec freeze test",
            "body": "Need a fake Hermes backend",
            "assignee": "docs",
            "workspace": "scratch",
            "branch": "hb/fake-hermes",
            "tenant": "public",
            "priority": 7,
            "created_by": "beads",
            "skills": ["github-code-review", "translation"],
            "max_retries": 3,
            "goal": True,
            "goal_max_turns": 9,
            "initial_status": "running",
            "idempotency_key": "abc",
        }
    )

    assert task_id == "task-123"
    assert _read_log(log_file) == [
        [
            "kanban",
            "create",
            "Spec freeze test",
            "--body",
            "Need a fake Hermes backend",
            "--assignee",
            "docs",
            "--workspace",
            "scratch",
            "--branch",
            "hb/fake-hermes",
            "--tenant",
            "public",
            "--priority",
            "7",
            "--created-by",
            "beads",
            "--idempotency-key",
            "abc",
            "--max-retries",
            "3",
            "--goal-max-turns",
            "9",
            "--initial-status",
            "running",
            "--goal",
            "--skill",
            "github-code-review",
            "--skill",
            "translation",
            "--json",
        ]
    ]


def test_show_returns_task_and_missing_task_is_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir, log_file = _install_fake_hermes(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_HERMES_LOG", str(log_file))

    backend = HermesKanbanBackend()
    task = backend.show("task-7")
    missing = backend.show("missing")

    assert task == {"id": "task-7", "status": "running", "title": "from fake hermes"}
    assert missing is None
    assert _read_log(log_file) == [
        ["kanban", "show", "task-7", "--json"],
        ["kanban", "show", "missing", "--json"],
    ]


def test_complete_constructs_kanban_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir, log_file = _install_fake_hermes(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_HERMES_LOG", str(log_file))

    backend = HermesKanbanBackend()
    backend.complete("task-7", "completed", "finished")

    assert _read_log(log_file) == [["kanban", "complete", "task-7", "--result", "completed", "--summary", "finished"]]


def test_create_failure_raises_before_follow_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir, log_file = _install_fake_hermes(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_HERMES_LOG", str(log_file))
    monkeypatch.setenv("FAKE_HERMES_CREATE_FAIL", "1")

    backend = HermesKanbanBackend()
    with pytest.raises(HermesKanbanBackendError, match="hermes kanban create broken task --json failed"):
        backend.create({"title": "broken task"})

    assert _read_log(log_file) == [["kanban", "create", "broken task", "--json"]]
