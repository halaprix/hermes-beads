"""Programmatic dispatch executor — callable from plugins without shelling out.

This module provides the dispatch apply flow as a pure Python function so
that the Hermes dashboard plugin (or any other caller) can dispatch beads
programmatically instead of shelling out to ``hb bridge dispatch``.
"""
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

from hermes_beads.dispatch_ops import (
    DispatchOpKind,
    build_dispatch_plan,
)
from hermes_beads.local_file_backend import LocalFileQueueBackend
from hermes_beads.cli import build_kanban_payload  # real payload builder with comments/assignee/status

# ---------------------------------------------------------------------------
# Thin bd subprocess wrappers (replicated from cli.py to avoid Click deps)
# ---------------------------------------------------------------------------


class DispatchError(RuntimeError):
    """Raised when dispatch fails for a recoverable reason."""


def _bd_json(args: list[str], cwd: str) -> Any:
    """Run ``bd`` with args in cwd and return parsed JSON."""
    cmd = ["bd"] + args
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, cwd=cwd,
        )
    except FileNotFoundError:
        raise DispatchError("bd not found on PATH")
    if result.returncode != 0:
        raise DispatchError(
            result.stderr.strip() or f"bd exited with code {result.returncode}"
        )
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError:
        snippet = (result.stdout[:200] + "...") if len(result.stdout or "") > 200 else (result.stdout or "<empty>")
        raise DispatchError(f"bd returned invalid JSON: {snippet}")


def _bd_run(args: list[str], cwd: str) -> str:
    """Run ``bd`` with args in cwd and return stdout."""
    cmd = ["bd"] + args
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, cwd=cwd,
            check=True,
        )
    except FileNotFoundError:
        raise DispatchError("bd not found on PATH")
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        msg = f"bd {shlex.join(args)} failed"
        if stderr:
            msg += f": {stderr}"
        raise DispatchError(msg) from exc
    return result.stdout


# ---------------------------------------------------------------------------
# Dispatch core (replicated from cli.py helpers, cwd-aware)
# ---------------------------------------------------------------------------


def _get_ready_beads(cwd: str) -> list[dict[str, Any]]:
    """Get ready beads via bd ready --json in the given project directory."""
    return list(_bd_json(["ready", "--json"], cwd) or [])


def _bead_is_linked(bead: dict[str, Any]) -> bool:
    """Check if metadata already contains hermes_kanban_task_id."""
    metadata = bead.get("metadata") or {}
    return bool(metadata.get("hermes_kanban_task_id"))


def _dispatch_candidates(ready_beads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter ready beads to those without a dispatch link."""
    return [b for b in ready_beads if not _bead_is_linked(b)]


def _write_dispatch_link(bead_id: str, task_id: str, cwd: str) -> None:
    """Write the dispatched task ID back to Beads metadata."""
    _bd_run(["update", bead_id, "--set-metadata", f"hermes_kanban_task_id={task_id}"], cwd)


def _gate_dispatch_bead(bead_id: str, cwd: str) -> None:
    """Mark a dispatched bead in_progress so it leaves the ready queue."""
    _bd_run(["update", bead_id, "--status", "in_progress"], cwd)


# The real payload builder (with comments, assignee mapping, status sync,
# metadata iteration) is imported from hermes_beads.cli at top of file.


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def dispatch_bead(
    bead_id: str,
    project_path: str,
    backend: str = "local-file",
    queue_file: str | None = None,
) -> dict[str, Any]:
    """Dispatch a single bead programmatically.

    Args:
        bead_id: The bead issue ID to dispatch (e.g. ``"hb-wua"``).
        project_path: Absolute path to the Beads project root.
        backend: Dispatch backend — ``"local-file"`` (default) or ``"hermes-cli"``.
        queue_file: Path to the queue file for ``local-file`` backend.
                    Defaults to ``<project_path>/.hermes-beads/queue.json``.

    Returns:
        A result dict with ``bead_id``, ``success``, ``output``, and ``task_id``.

    Raises:
        DispatchError: If the bead is not ready, already linked, or dispatch fails.
    """
    cwd = str(Path(project_path).resolve())

    # 1. Get ready beads and filter to the target
    ready = _get_ready_beads(cwd)
    matching = [b for b in ready if b.get("id") == bead_id]
    if not matching:
        raise DispatchError(f"Bead '{bead_id}' is not in the ready queue")

    # 2. Filter to candidates (not already linked)
    candidates = _dispatch_candidates(matching)
    if not candidates:
        raise DispatchError(f"Bead '{bead_id}' is already linked to a Kanban task")

    # 3. Build dispatch plan using the real payload builder
    plan = build_dispatch_plan(candidates, payload_builder=build_kanban_payload)
    create_ops = [op for op in plan if op.kind is DispatchOpKind.CREATE]
    if not create_ops:
        raise DispatchError(f"No dispatchable operations for bead '{bead_id}'")

    # 4. Create dispatch backend
    if backend == "local-file":
        qf = Path(queue_file) if queue_file else Path(cwd) / ".hermes-beads" / "queue.json"
        qf.parent.mkdir(parents=True, exist_ok=True)
        dispatch_backend: Any = LocalFileQueueBackend(qf, project_root=Path(cwd))
    elif backend == "hermes-cli":
        from hermes_beads.hermes_kanban_backend import HermesKanbanBackend
        dispatch_backend = HermesKanbanBackend()
    else:
        raise DispatchError(f"Unsupported backend: {backend}")

    # 5. Apply each CREATE operation
    results = []
    for op in create_ops:
        try:
            task_id = dispatch_backend.create(op.payload)
            bid = str(op.payload.get("source_bead_id", ""))
            if bid:
                _write_dispatch_link(bid, task_id, cwd)
                _gate_dispatch_bead(bid, cwd)
            results.append({
                "bead_id": bid or bead_id,
                "success": True,
                "task_id": task_id,
                "output": f"Dispatched as task {task_id}",
            })
        except Exception as exc:
            results.append({
                "bead_id": bead_id,
                "success": False,
                "output": str(exc),
            })

    return results[0] if results else {"bead_id": bead_id, "success": False, "output": "No operations"}
