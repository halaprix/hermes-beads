"""Local-file dispatch backend for hermes-beads.

The local-file backend is a deterministic, disposable queue used to exercise
bridge dispatch without a live Hermes Kanban instance. Beads remains the source
of truth; this file is only a derived execution artifact.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class LocalFileQueueError(RuntimeError):
    """Raised when the local-file dispatch queue cannot be read or written."""


def resolve_queue_file(queue_file: str | Path, project_root: str | Path | None = None) -> Path:
    """Resolve a queue-file path.

    Relative paths are resolved against ``project_root`` (or the current working
    directory when omitted). Absolute paths are preserved. The returned path is
    absolute and normalized without requiring the file to exist.
    """
    path = Path(queue_file)
    if path.is_absolute():
        return path.resolve()
    root = Path(project_root) if project_root is not None else Path.cwd()
    return (root / path).resolve()


def _canonical_json(value: Any) -> str:
    """Return stable JSON used for hashing and file output."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_local_task_id(payload: dict[str, Any]) -> str:
    """Build a stable local task ID from a Kanban-shaped payload."""
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:12]
    return f"local-{digest}"


class LocalFileQueueBackend:
    """Dispatch backend that appends Kanban-like task records to JSON.

    Queue file format:

    ``{"tasks": [{"id": "local-...", "status": "queued", "payload": {...}}]}``

    ``create`` is idempotent for a stable task ID: if the same payload was
    already written, the existing ID is returned and the queue is left unchanged.
    """

    def __init__(self, queue_file: str | Path, project_root: str | Path | None = None) -> None:
        self.queue_file = resolve_queue_file(queue_file, project_root=project_root)

    def create(self, payload: dict[str, Any]) -> str:
        """Append a queued task record unless the stable task ID already exists."""
        task_id = build_local_task_id(payload)
        queue = self._read_queue()
        tasks = queue["tasks"]

        for task in tasks:
            if isinstance(task, dict) and task.get("id") == task_id:
                return task_id

        tasks.append({"id": task_id, "status": "queued", "payload": payload})
        self._write_queue(queue)
        return task_id

    def show(self, task_id: str) -> dict[str, Any] | None:
        """Return a queued task by ID, or ``None`` if it is absent."""
        for task in self._read_queue()["tasks"]:
            if isinstance(task, dict) and task.get("id") == task_id:
                return task
        return None

    def complete(self, task_id: str, status: str, summary: str) -> None:
        """Record completion fields for a queued task.

        This method exists to satisfy the broader ``DispatchBackend`` protocol.
        Result-sync work may use it later; dispatch planning and creation do not
        depend on it.
        """
        queue = self._read_queue()
        for task in queue["tasks"]:
            if isinstance(task, dict) and task.get("id") == task_id:
                task["status"] = status
                task["summary"] = summary
                self._write_queue(queue)
                return
        raise LocalFileQueueError(f"task not found in local queue: {task_id}")

    def _read_queue(self) -> dict[str, list[dict[str, Any]]]:
        if not self.queue_file.exists():
            return {"tasks": []}
        try:
            data = json.loads(self.queue_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise LocalFileQueueError(f"invalid JSON queue file: {self.queue_file}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
            raise LocalFileQueueError(f"invalid queue file shape: {self.queue_file}")
        return data

    def _write_queue(self, queue: dict[str, list[dict[str, Any]]]) -> None:
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        self.queue_file.write_text(
            json.dumps(queue, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
