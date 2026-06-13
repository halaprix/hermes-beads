"""Tests for the local-file dispatch queue backend.

The local-file backend is a disposable dispatch target: it records the
Kanban-shaped payloads that would be sent to Hermes, using stable task IDs so
re-running dispatch can skip duplicates.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_beads.local_file_backend import (
    LocalFileQueueBackend,
    LocalFileQueueError,
    build_local_task_id,
    resolve_queue_file,
)


def _payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "source": "beads",
        "source_bead_id": "hb-local",
        "title": "hb-local: Local file backend",
        "assignee": "ts-dev",
        "priority": 1,
        "mode": "pr",
        "body": json.dumps({"bead_id": "hb-local", "goal": "Local file backend"}),
    }
    data.update(overrides)
    return data


def test_empty_queue_file_is_created_on_first_create(tmp_path: Path) -> None:
    queue_file = tmp_path / "queue" / "dispatch.json"
    backend = LocalFileQueueBackend(queue_file)

    task_id = backend.create(_payload())

    assert task_id == build_local_task_id(_payload())
    data = json.loads(queue_file.read_text())
    assert data == {
        "tasks": [
            {
                "id": task_id,
                "status": "queued",
                "payload": _payload(),
            }
        ]
    }


def test_create_appends_distinct_payloads(tmp_path: Path) -> None:
    queue_file = tmp_path / "dispatch.json"
    backend = LocalFileQueueBackend(queue_file)

    first_id = backend.create(_payload(source_bead_id="hb-a", title="hb-a: A"))
    second_id = backend.create(_payload(source_bead_id="hb-b", title="hb-b: B"))

    data = json.loads(queue_file.read_text())
    assert [task["id"] for task in data["tasks"]] == [first_id, second_id]
    assert data["tasks"][0]["payload"]["source_bead_id"] == "hb-a"
    assert data["tasks"][1]["payload"]["source_bead_id"] == "hb-b"


def test_duplicate_stable_task_id_is_skipped(tmp_path: Path) -> None:
    queue_file = tmp_path / "dispatch.json"
    backend = LocalFileQueueBackend(queue_file)
    payload = _payload()

    first_id = backend.create(payload)
    second_id = backend.create(dict(payload))

    data = json.loads(queue_file.read_text())
    assert second_id == first_id
    assert len(data["tasks"]) == 1


def test_corrupt_queue_file_raises_clear_error(tmp_path: Path) -> None:
    queue_file = tmp_path / "dispatch.json"
    queue_file.write_text("not json")
    backend = LocalFileQueueBackend(queue_file)

    with pytest.raises(LocalFileQueueError, match="invalid JSON queue file"):
        backend.create(_payload())


def test_project_relative_queue_file_resolves_against_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()

    resolved = resolve_queue_file(".hermes-beads/queue.json", project_root=project_root)
    backend = LocalFileQueueBackend(".hermes-beads/queue.json", project_root=project_root)
    task_id = backend.create(_payload())

    assert resolved == project_root / ".hermes-beads" / "queue.json"
    assert backend.queue_file == resolved
    assert json.loads(resolved.read_text())["tasks"][0]["id"] == task_id


def test_task_id_is_independent_of_payload_key_order() -> None:
    payload = _payload()
    reordered = {key: payload[key] for key in reversed(list(payload.keys()))}

    assert build_local_task_id(payload) == build_local_task_id(reordered)
