"""Bridge tick planning, locking, and public-safe summaries.

A tick is one conservative controller pass: optionally run local preflight
checks, dispatch ready Beads work to a backend, and sync any provided worker
results back into Beads. The helpers here keep planning and safety policy
separate from the Click adapter in ``cli.py``.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


class TickLockError(RuntimeError):
    """Raised when a bridge tick lock cannot be acquired safely."""


@dataclass(frozen=True, slots=True)
class TickOperation:
    """A planned bridge tick operation."""

    op: str
    count: int = 0
    backend: str = ""
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable operation record."""
        data: dict[str, Any] = {"op": self.op, "count": self.count}
        if self.backend:
            data["backend"] = self.backend
        if self.path:
            data["path"] = self.path
        return data


@dataclass(frozen=True, slots=True)
class TickPlan:
    """A dry-run/apply-neutral tick plan."""

    operations: tuple[TickOperation, ...]
    dispatch_count: int
    result_count: int
    backend: str
    queue_file: str = ""

    @property
    def is_noop(self) -> bool:
        """Return whether the tick has no work to apply."""
        return self.dispatch_count == 0 and self.result_count == 0

    def to_dict(self) -> dict[str, Any]:
        """Return a public-safe JSON representation of the tick plan."""
        return {
            "operations": [op.to_dict() for op in self.operations],
            "summary": tick_summary(self),
        }


def count_results(results: Any) -> int:
    """Return the number of result records in a result-sync payload."""
    if isinstance(results, dict):
        results = results.get("results", [])
    if isinstance(results, list):
        return len(results)
    return 0


def build_tick_plan(
    dispatch_beads: Iterable[dict[str, Any]],
    results: Any | None,
    *,
    backend: str,
    queue_file: str = "",
) -> TickPlan:
    """Build a public-safe bridge tick plan without mutating state."""
    dispatch_count = sum(1 for _ in dispatch_beads)
    result_count = count_results(results)
    operations: list[TickOperation] = []
    if dispatch_count:
        operations.append(TickOperation("dispatch", dispatch_count, backend=backend, path=queue_file))
    if result_count:
        operations.append(TickOperation("sync-results", result_count))
    return TickPlan(tuple(operations), dispatch_count, result_count, backend, queue_file)


def tick_summary(plan: TickPlan, *, applied: bool = False) -> dict[str, Any]:
    """Return a public-safe summary for human and cron output."""
    return {
        "applied": applied,
        "noop": plan.is_noop,
        "dispatch_count": plan.dispatch_count,
        "result_count": plan.result_count,
        "backend": plan.backend,
    }


def load_results_file(path: str | Path | None) -> Any | None:
    """Load a JSON results file, returning ``None`` when no file was requested."""
    if path is None:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


class TickLock:
    """Filesystem lock for one bridge tick process."""

    def __init__(self, path: str | Path, *, stale_after_seconds: int = 3600) -> None:
        self.path = Path(path)
        self.stale_after_seconds = stale_after_seconds
        self.acquired = False

    def acquire(self) -> None:
        """Acquire the lock, replacing it only when it is stale."""
        now = int(time.time())
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                created_at = int(data.get("created_at", 0))
            except (json.JSONDecodeError, TypeError, ValueError):
                created_at = 0
            age = now - created_at
            if age < self.stale_after_seconds:
                raise TickLockError(f"tick lock is held: {self.path}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"pid": os.getpid(), "created_at": now}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.acquired = True

    def release(self) -> None:
        """Release the lock if this instance acquired it."""
        if self.acquired and self.path.exists():
            self.path.unlink()
        self.acquired = False

    def __enter__(self) -> "TickLock":
        """Acquire the lock for a context manager."""
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Release the lock at context exit."""
        self.release()
