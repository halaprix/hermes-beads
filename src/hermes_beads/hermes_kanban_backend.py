"""Hermes Kanban subprocess backend for hermes-beads.

This backend is intentionally thin: it shells out to the real `hermes`
CLI, captures stdout/stderr, and translates the current command contract
into a small Python protocol. Tests inject a fake `hermes` executable in
`PATH` so CI never depends on a live Hermes install.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


class HermesKanbanBackendError(RuntimeError):
    """Raised when the Hermes Kanban CLI cannot satisfy a backend call."""


@dataclass(slots=True)
class HermesKanbanBackend:
    """Subprocess backend for the `hermes kanban` CLI."""

    executable: str = "hermes"
    cwd: str | Path | None = None
    env: Mapping[str, str] | None = None
    _resolved_executable: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._resolved_executable = self._resolve_executable(self.executable)

    @staticmethod
    def _resolve_executable(executable: str) -> str:
        path = Path(executable)
        if path.is_absolute() or path.parent != Path("."):
            if not path.exists():
                raise HermesKanbanBackendError(f"hermes executable not found: {path}")
            return str(path)
        resolved = shutil.which(executable)
        if resolved is None:
            raise HermesKanbanBackendError(
                "hermes command not found on PATH. Is Hermes Agent installed?"
            )
        return resolved

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                [self._resolved_executable, "kanban", *args],
                cwd=self.cwd,
                env={**os.environ, **(dict(self.env) if self.env is not None else {})},
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:  # pragma: no cover - belt and suspenders
            raise HermesKanbanBackendError(
                "hermes command not found on PATH. Is Hermes Agent installed?"
            ) from exc

    @staticmethod
    def _raise_process_error(args: list[str], proc: subprocess.CompletedProcess[str]) -> None:
        stderr = proc.stderr.strip() if proc.stderr else ""
        cmd = "hermes kanban " + " ".join(args)
        message = f"{cmd} failed"
        if stderr:
            message += f": {stderr}"
        raise HermesKanbanBackendError(message)

    @staticmethod
    def _parse_json(stdout: str, command: str) -> Any:
        try:
            return json.loads(stdout or "null")
        except json.JSONDecodeError as exc:
            snippet = (stdout[:200] + "...") if len(stdout or "") > 200 else (stdout or "<empty>")
            raise HermesKanbanBackendError(
                f"hermes kanban {command} returned invalid JSON: {exc}. Output: {snippet}"
            ) from exc

    @staticmethod
    def _is_missing_task(stderr: str) -> bool:
        return "no such task:" in (stderr or "")

    def create(self, payload: dict[str, Any]) -> str:
        """Create a Kanban task and return the task id."""
        if "title" not in payload:
            raise HermesKanbanBackendError("payload missing required title")
        args = ["create", str(payload["title"])]

        def add(flag: str, key: str) -> None:
            """Append one optional CLI flag when payload contains a value."""
            value = payload.get(key)
            if value is None or value == "":
                return
            args.extend([flag, str(value)])

        add("--body", "body")
        add("--assignee", "assignee")
        add("--workspace", "workspace")
        add("--branch", "branch")
        add("--tenant", "tenant")
        add("--priority", "priority")
        add("--created-by", "created_by")
        add("--idempotency-key", "idempotency_key")
        add("--max-runtime", "max_runtime")
        add("--max-retries", "max_retries")
        add("--goal-max-turns", "goal_max_turns")
        add("--initial-status", "initial_status")

        if payload.get("goal"):
            args.append("--goal")
        for skill in payload.get("skills", []) or []:
            args.extend(["--skill", str(skill)])

        args.append("--json")
        proc = self._run(args)
        if proc.returncode != 0:
            self._raise_process_error(args, proc)
        data = self._parse_json(proc.stdout, "create")
        if isinstance(data, dict) and data.get("id"):
            return str(data["id"])
        raise HermesKanbanBackendError("hermes kanban create did not return a task id")

    def show(self, task_id: str) -> dict[str, Any] | None:
        """Return the current task state, or ``None`` when the task is missing."""
        args = ["show", task_id, "--json"]
        proc = self._run(args)
        if proc.returncode != 0:
            if self._is_missing_task(proc.stderr):
                return None
            self._raise_process_error(args, proc)
        if self._is_missing_task(proc.stderr) and not (proc.stdout or "").strip():
            return None
        data = self._parse_json(proc.stdout, "show")
        if isinstance(data, dict):
            if "task" in data and isinstance(data["task"], dict):
                return data["task"]
            return data
        raise HermesKanbanBackendError("hermes kanban show returned non-object JSON")

    def complete(self, task_id: str, status: str, summary: str) -> None:
        """Mark a task complete or failed using the CLI contract."""
        args = ["complete", task_id, "--result", status, "--summary", summary]
        proc = self._run(args)
        if proc.returncode != 0:
            self._raise_process_error(args, proc)
