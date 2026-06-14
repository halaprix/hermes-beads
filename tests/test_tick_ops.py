"""Tests for bridge tick planning and locking."""

from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Barrier, Thread

import pytest

from hermes_beads.tick_ops import TickLock, TickLockError, build_tick_plan


def test_tick_plan_noop() -> None:
    plan = build_tick_plan([], None, backend="local-file", queue_file="queue.json")
    assert plan.is_noop is True
    assert plan.to_dict()["summary"]["dispatch_count"] == 0
    assert plan.to_dict()["operations"] == []


def test_tick_plan_dispatch_only() -> None:
    plan = build_tick_plan([{"id": "hb-a"}], None, backend="local-file", queue_file="queue.json")
    assert plan.is_noop is False
    assert plan.to_dict()["operations"] == [
        {"op": "dispatch", "count": 1, "backend": "local-file", "path": "queue.json"}
    ]


def test_tick_plan_sync_only() -> None:
    plan = build_tick_plan([], [{"bead_id": "hb-a"}], backend="local-file")
    assert plan.to_dict()["operations"] == [{"op": "sync-results", "count": 1}]


def test_tick_plan_dispatch_and_sync() -> None:
    plan = build_tick_plan([{"id": "hb-a"}], {"results": [{"bead_id": "hb-a"}]}, backend="hermes-cli")
    assert [op["op"] for op in plan.to_dict()["operations"]] == ["dispatch", "sync-results"]


def test_tick_lock_held_exits_without_replacing(tmp_path: Path) -> None:
    lock = tmp_path / "tick.lock"
    lock.write_text(json.dumps({"pid": 123, "created_at": int(time.time())}), encoding="utf-8")
    before = lock.read_text(encoding="utf-8")
    with pytest.raises(TickLockError):
        TickLock(lock, stale_after_seconds=3600).acquire()
    assert lock.read_text(encoding="utf-8") == before


def test_tick_lock_recovers_stale_lock(tmp_path: Path) -> None:
    lock = tmp_path / "tick.lock"
    lock.write_text(json.dumps({"pid": 123, "created_at": 1}), encoding="utf-8")
    tick_lock = TickLock(lock, stale_after_seconds=1)
    tick_lock.acquire()
    assert json.loads(lock.read_text(encoding="utf-8"))["pid"] != 123
    tick_lock.release()
    assert not lock.exists()


def test_tick_lock_allows_only_one_concurrent_acquirer(tmp_path: Path) -> None:
    lock = tmp_path / "tick.lock"
    barrier = Barrier(2)
    results: list[str] = []

    def attempt() -> None:
        tick_lock = TickLock(lock, stale_after_seconds=3600)
        barrier.wait()
        try:
            tick_lock.acquire()
        except TickLockError:
            results.append("blocked")
        else:
            results.append("acquired")

    threads = [Thread(target=attempt), Thread(target=attempt)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == ["acquired", "blocked"]
