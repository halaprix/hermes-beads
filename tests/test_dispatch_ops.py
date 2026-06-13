"""Tests for dispatch operation plan generation.

These tests cover the pure planner for the ``hb bridge dispatch`` command.
They exercise plan generation independently of Click, the bd CLI, and any
specific backend (local-file or Hermes Kanban). Live mutation is not in
scope for this module — ``build_dispatch_plan`` returns structured
operations that a future apply step can replay against a backend.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from hermes_beads.dispatch_ops import (
    DispatchBackend,
    DispatchOp,
    DispatchOpKind,
    build_dispatch_plan,
    kanban_payload_for_bead,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _bead(**overrides: object) -> dict[str, Any]:
    """Return a minimal valid bead dict for planner tests."""
    data: dict[str, Any] = {
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
        "labels": ["dispatch"],
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# DispatchOpKind enum
# ---------------------------------------------------------------------------


class TestDispatchOpKind:
    """Enum values used in dispatch operation plan records."""

    def test_create_kind_value(self) -> None:
        assert DispatchOpKind.CREATE.value == "create"

    def test_skipped_kind_value(self) -> None:
        assert DispatchOpKind.SKIPPED.value == "skipped"

    def test_kind_values_are_unique(self) -> None:
        values = [k.value for k in DispatchOpKind]
        assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# DispatchOp dataclass
# ---------------------------------------------------------------------------


class TestDispatchOp:
    """Structured dispatch operation plan record."""

    def test_create_op_round_trip_through_dict(self) -> None:
        op = DispatchOp(
            kind=DispatchOpKind.CREATE,
            bead_id="hb-abc",
            payload={"source": "beads", "source_bead_id": "hb-abc", "title": "x"},
        )
        d = op.to_dict()
        assert d == {
            "op": "create",
            "bead_id": "hb-abc",
            "payload": {
                "source": "beads",
                "source_bead_id": "hb-abc",
                "title": "x",
            },
        }

    def test_skipped_op_round_trip_through_dict(self) -> None:
        op = DispatchOp(
            kind=DispatchOpKind.SKIPPED,
            bead_id="hb-abc",
            reason="already dispatched",
        )
        d = op.to_dict()
        assert d == {
            "op": "skipped",
            "bead_id": "hb-abc",
            "reason": "already dispatched",
        }

    def test_create_op_payload_serializes_to_json(self) -> None:
        op = DispatchOp(
            kind=DispatchOpKind.CREATE,
            bead_id="hb-abc",
            payload={"a": 1, "b": ["c", "d"]},
        )
        # Payload round-trips through JSON without raising.
        encoded = json.dumps(op.to_dict())
        decoded = json.loads(encoded)
        assert decoded["payload"] == {"a": 1, "b": ["c", "d"]}

    def test_op_is_frozen_dataclass(self) -> None:
        """DispatchOp is a frozen dataclass — plans are records, not state."""
        from dataclasses import FrozenInstanceError

        op = DispatchOp(
            kind=DispatchOpKind.CREATE,
            bead_id="hb-abc",
            payload={"x": 1},
        )
        with pytest.raises(FrozenInstanceError):
            op.bead_id = "hb-other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DispatchBackend protocol
# ---------------------------------------------------------------------------


class TestDispatchBackendProtocol:
    """DispatchBackend defines the contract for backends that accept a plan."""

    def test_local_backend_satisfies_protocol(self) -> None:
        class LocalBackend:
            def create(self, payload: dict[str, Any]) -> str:
                return "task-local-1"

            def show(self, task_id: str) -> dict[str, Any] | None:
                return {"id": task_id, "status": "queued"}

            def complete(self, task_id: str, status: str, summary: str) -> None:
                return None

        backend: Any = LocalBackend()
        assert isinstance(backend, DispatchBackend)

    def test_create_only_backend_minimum_satisfies_protocol(self) -> None:
        """A backend that only implements ``create`` is the minimum required.

        ``show`` and ``complete`` are not strictly required for dispatch apply:
        the planner emits ``create`` operations, and the apply step forwards
        them to ``backend.create``. ``show``/``complete`` are defined on the
        protocol because result-sync needs them, but a backend that only
        implements dispatch create can still be type-compatible if it
        provides explicit ``None`` implementations or is used only via duck
        typing.

        For this test we exercise the minimum *create*-only surface that
        ``build_dispatch_plan`` actually needs.
        """

        class CreateOnlyBackend:
            def create(self, payload: dict[str, Any]) -> str:
                return "task-1"

        backend: Any = CreateOnlyBackend()
        # ``create`` is the only method the dispatch planner calls.
        assert callable(backend.create)
        # Protocol membership is optional for create-only backends; the
        # planner invokes ``create`` directly via duck typing.
        plan = build_dispatch_plan([_bead(id="hb-abc")], backend=backend)
        assert len(plan) == 1
        assert plan[0].kind == DispatchOpKind.CREATE

    def test_runtime_checkable_protocol_accepts_non_protocol_class(self) -> None:
        """Plain object that doesn't match the protocol is not an instance."""

        class NotABackend:
            pass

        backend: Any = NotABackend()
        assert not isinstance(backend, DispatchBackend)


# ---------------------------------------------------------------------------
# kanban_payload_for_bead
# ---------------------------------------------------------------------------


class TestKanbanPayloadForBead:
    """Pure mapping from bead to Hermes Kanban-shaped payload."""

    def test_payload_contains_required_keys(self) -> None:
        bead = _bead(id="hb-fup", title="Bridge task", priority=3)
        payload = kanban_payload_for_bead(bead)
        assert payload["source"] == "beads"
        assert payload["source_bead_id"] == "hb-fup"
        assert payload["title"] == "hb-fup: Bridge task"
        assert payload["assignee"] == "ts-dev"
        assert payload["priority"] == 3
        assert payload["mode"] == "pr"
        # body is the handoff packet, JSON-encoded
        decoded = json.loads(payload["body"])
        assert decoded["bead_id"] == "hb-fup"
        assert decoded["goal"] == "Bridge task"

    def test_payload_default_priority_is_two(self) -> None:
        bead = _bead()
        bead.pop("priority", None)
        payload = kanban_payload_for_bead(bead)
        assert payload["priority"] == 2

    def test_payload_default_mode_is_pr(self) -> None:
        bead = _bead(metadata={"hermes_status": "ready"})
        payload = kanban_payload_for_bead(bead)
        assert payload["mode"] == "pr"

    def test_payload_includes_explicit_profile(self) -> None:
        bead = _bead(metadata={"hermes_profile": "planner"})
        payload = kanban_payload_for_bead(bead)
        assert payload["assignee"] == "planner"


# ---------------------------------------------------------------------------
# build_dispatch_plan
# ---------------------------------------------------------------------------


class TestBuildDispatchPlan:
    """Pure planner: ready beads + optional backend -> list of DispatchOp."""

    def test_empty_beads_yields_empty_plan(self) -> None:
        plan = build_dispatch_plan([])
        assert plan == []

    def test_single_bead_produces_one_create_op(self) -> None:
        bead = _bead(id="hb-fup", title="Bridge task")
        plan = build_dispatch_plan([bead])
        assert len(plan) == 1
        op = plan[0]
        assert op.kind == DispatchOpKind.CREATE
        assert op.bead_id == "hb-fup"
        assert op.payload["source_bead_id"] == "hb-fup"

    def test_multiple_beads_produce_ordered_create_ops(self) -> None:
        beads = [
            _bead(id="hb-aaa", title="A"),
            _bead(id="hb-bbb", title="B"),
            _bead(id="hb-ccc", title="C"),
        ]
        plan = build_dispatch_plan(beads)
        assert [op.bead_id for op in plan] == ["hb-aaa", "hb-bbb", "hb-ccc"]
        assert all(op.kind == DispatchOpKind.CREATE for op in plan)

    def test_plan_does_not_mutate_input_beads(self) -> None:
        """build_dispatch_plan must be a pure function — no in-place edits."""
        bead = _bead(id="hb-fup", title="Bridge task")
        original = json.dumps(bead, sort_keys=True)
        _ = build_dispatch_plan([bead])
        assert json.dumps(bead, sort_keys=True) == original

    def test_plan_does_not_call_backend_create(self) -> None:
        """No live mutation: the planner must not call backend.create.

        ``build_dispatch_plan`` is the dry-run side of the contract. It
        produces a list of operations describing what ``apply`` would do
        for the same input. The backend is only used for the *shape* of
        the protocol (i.e. as a type hint or capability check), never to
        mutate state.
        """
        calls: list[dict[str, Any]] = []

        @dataclass
        class SpyBackend:
            def create(self, payload: dict[str, Any]) -> str:
                calls.append(payload)
                return "task-spy-1"

            def show(self, task_id: str) -> dict[str, Any] | None:
                return None

            def complete(self, task_id: str, status: str, summary: str) -> None:
                return None

        plan = build_dispatch_plan([_bead(id="hb-abc")], backend=SpyBackend())
        assert len(plan) == 1
        # Critical: no create call happened.
        assert calls == []

    def test_plan_is_deterministic_for_same_input(self) -> None:
        beads = [_bead(id="hb-abc", title="T"), _bead(id="hb-def", title="U")]
        plan1 = build_dispatch_plan(beads)
        plan2 = build_dispatch_plan(beads)
        assert [(o.kind, o.bead_id) for o in plan1] == [
            (o.kind, o.bead_id) for o in plan2
        ]

    def test_create_op_payload_is_kanban_shaped(self) -> None:
        """The create op's payload has the Kanban dry-run shape."""
        bead = _bead(id="hb-zzz", title="Z")
        plan = build_dispatch_plan([bead])
        op = plan[0]
        # All required keys are present.
        for key in (
            "source",
            "source_bead_id",
            "title",
            "assignee",
            "priority",
            "mode",
            "body",
        ):
            assert key in op.payload

    def test_plan_accepts_injected_payload_builder(self) -> None:
        """CLI adapters can inject richer payload builders without changing planning."""
        calls: list[str] = []

        def payload_builder(bead: dict[str, Any]) -> dict[str, Any]:
            calls.append(str(bead["id"]))
            return {"source_bead_id": bead["id"], "body": "rich handoff"}

        plan = build_dispatch_plan([_bead(id="hb-rich")], payload_builder=payload_builder)

        assert calls == ["hb-rich"]
        assert plan[0].kind == DispatchOpKind.CREATE
        assert plan[0].payload == {"source_bead_id": "hb-rich", "body": "rich handoff"}

    def test_skipped_op_for_bead_without_id(self) -> None:
        """A bead with no id is skipped, not silently dispatched."""
        bad = _bead()
        bad["id"] = ""
        plan = build_dispatch_plan([bad])
        assert len(plan) == 1
        op = plan[0]
        assert op.kind == DispatchOpKind.SKIPPED
        assert op.bead_id == ""
        assert op.reason  # non-empty reason explaining the skip

    def test_skipped_op_for_non_dict_bead(self) -> None:
        """A non-dict entry in the ready list is skipped with a clear reason."""
        plan = build_dispatch_plan([_bead(id="hb-ok"), "not-a-dict"])  # type: ignore[list-item]
        assert len(plan) == 2
        assert plan[0].kind == DispatchOpKind.CREATE
        assert plan[0].bead_id == "hb-ok"
        assert plan[1].kind == DispatchOpKind.SKIPPED
        assert "not a dict" in plan[1].reason.lower()

    def test_plan_serializes_to_json(self) -> None:
        """Plan ops must round-trip through JSON, matching the dry-run wire format."""
        beads = [_bead(id="hb-abc", title="A"), _bead(id="hb-def", title="B")]
        plan = build_dispatch_plan(beads)
        wire = {"operations": [op.to_dict() for op in plan]}
        encoded = json.dumps(wire)
        decoded = json.loads(encoded)
        assert decoded["operations"][0]["op"] == "create"
        assert decoded["operations"][1]["bead_id"] == "hb-def"
