"""Dispatch operation planning for the ``hb bridge dispatch`` command.

This module owns the *pure* planning side of the dispatch command: it
maps ready Beads issues into structured ``DispatchOp`` records that
describe what a future apply step would do against a ``DispatchBackend``.

Design goals (see bead hb-17h.1):

- The planner is a pure function — no Click, no bd CLI, no network/IO,
  no live mutation. ``build_dispatch_plan`` only ever *describes* a plan;
  a separate apply step is responsible for replaying it against a
  backend.
- The ``DispatchBackend`` protocol defines the contract that backends
  must implement. The minimum surface needed for dispatch apply is
  ``create``; ``show`` and ``complete`` are defined for forward
  compatibility with result-sync and are not invoked by the planner.
- Beads remains the single source of truth: dispatch is a one-way
  projection from Beads issues to backend task records.

The dry-run wire format produced here is intentionally close to the
existing ``bridge dispatch --dry-run`` JSON so CLI consumers see no
behavioral change. The CLI command is reduced to a thin adapter that
imports this module.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Protocol, runtime_checkable


class DispatchOpKind(str, Enum):
    """Kinds of dispatch operations emitted by :func:`build_dispatch_plan`.

    Inheriting from ``str`` keeps the on-the-wire JSON for ``op`` a
    human-readable string (``"create"`` / ``"skipped"``) while still
    allowing ``is`` checks in tests.
    """

    CREATE = "create"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class DispatchOp:
    """A single, immutable dispatch operation plan record.

    Attributes
    ----------
    kind:
        The kind of operation (create or skipped).
    bead_id:
        The Beads issue ID this operation targets. Empty for skipped
        operations whose target bead is unknown or invalid.
    payload:
        The Kanban-shaped payload that would be sent to a backend on
        apply. Only meaningful for ``CREATE`` operations; ``SKIPPED``
        operations leave this empty.
    reason:
        Human-readable reason for a ``SKIPPED`` operation. Empty for
        ``CREATE`` operations.
    """

    kind: DispatchOpKind
    bead_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Render the op as the dry-run wire format.

        ``CREATE`` ops include the payload under ``"payload"``.
        ``SKIPPED`` ops include the reason under ``"reason"``.
        Both always include ``"op"`` and ``"bead_id"``.
        """
        out: dict[str, Any] = {"op": self.kind.value, "bead_id": self.bead_id}
        if self.kind is DispatchOpKind.CREATE:
            out["payload"] = self.payload
        else:
            out["reason"] = self.reason
        return out


@runtime_checkable
class DispatchBackend(Protocol):
    """Protocol for backends that accept a dispatch plan.

    ``create`` is the minimum required surface: the dispatch apply step
    replays each ``CREATE`` op by calling ``backend.create(payload)``.

    ``show`` and ``complete`` are not invoked by the planner. They are
    declared on the protocol so a single backend object can serve both
    the dispatch and result-sync flows. A backend is free to implement
    only ``create`` for dispatch-apply; the apply step uses duck typing
    for the surface it actually needs.
    """

    def create(self, payload: dict[str, Any]) -> str:
        """Submit a Kanban-shaped payload to the backend.

        Returns
        -------
        str
            A backend-assigned task ID (e.g. ``"task-123"`` for the
            Hermes Kanban backend, or a stable hash for a local-file
            backend).
        """
        ...

    def show(self, task_id: str) -> dict[str, Any] | None:
        """Fetch the current state of a task previously created by ``create``."""
        ...

    def complete(self, task_id: str, status: str, summary: str) -> None:
        """Mark a task as completed/failed with a human-readable summary."""
        ...


# ---------------------------------------------------------------------------
# Pure helpers (no IO, no Click). These are duplicated in :mod:`hermes_beads.cli`
# to keep this module importable without dragging in Click; if the cli-side
# helpers change, mirror the change here.
# ---------------------------------------------------------------------------


def _explain_profile_selection(bead: dict[str, Any]) -> tuple[str, str]:
    """Choose a Hermes profile and explain the routing rule.

    Mirrors ``explain_profile_selection`` in :mod:`hermes_beads.cli`.
    Kept in sync deliberately — the planner must not depend on Click,
    and the policy is small and stable.
    """
    metadata = bead.get("metadata", {}) or {}
    explicit = metadata.get("hermes_profile")
    if explicit:
        return str(explicit), "explicit metadata.hermes_profile"

    labels = set(bead.get("labels", []) or [])
    if "docs" in labels:
        return "docs", "labels include docs"
    if "planning" in labels or "architecture" in labels:
        return "planner", "labels include planning or architecture"
    return "ts-dev", "default profile"


def _select_profile(bead: dict[str, Any]) -> str:
    """Return the Hermes profile string for a bead.

    Mirrors ``select_profile`` in :mod:`hermes_beads.cli`.
    """
    profile, _reason = _explain_profile_selection(bead)
    return profile


def _handoff_packet_shape(bead: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal handoff-packet shape suitable for the Kanban body.

    This is a planning-time approximation: the full handoff packet (with
    comments and dependency summaries) is built by the ``handoff`` CLI
    command, which performs IO. The dispatch planner only needs the
    stable fields (``bead_id``, ``goal``, ``hermes_profile``, etc.) for
    the Kanban task body, so we build that subset here without IO.
    """
    metadata = bead.get("metadata", {}) or {}
    bead_id = str(bead.get("id", "") or "")
    profile, _reason = _explain_profile_selection(bead)
    return {
        "bead_id": bead_id,
        "goal": bead.get("title", ""),
        "description": bead.get("description", ""),
        "stop_condition": metadata.get("hermes_stop_condition", ""),
        "hermes_profile": profile,
        "hermes_mode": metadata.get("hermes_mode", ""),
        "dependencies": [
            {
                "id": str(dep.get("id", "")),
                "title": str(dep.get("title", "")),
                "status": str(dep.get("status", "")),
            }
            for dep in (bead.get("dependencies", []) or [])
        ],
        "comments": [],
        "iteration": int(metadata.get("hermes_iteration", 0) or 0),
    }


def kanban_payload_for_bead(bead: dict[str, Any]) -> dict[str, Any]:
    """Map a ready Beads issue to a Hermes Kanban-shaped payload.

    This is the single source of truth for the bead -> Kanban payload
    shape. ``bridge dispatch --dry-run`` emits these payloads in its
    ``tasks`` list. The legacy ``build_kanban_payload`` in
    :mod:`hermes_beads.cli` is preserved as a thin wrapper for
    backward compatibility with any direct importers; both functions
    must produce the same shape.
    """
    if not isinstance(bead, dict):
        raise TypeError(f"bead must be a dict, got {type(bead).__name__}")
    packet = _handoff_packet_shape(bead)
    bead_id = str(packet.get("bead_id", "") or "")
    profile = _select_profile(bead)
    return {
        "source": "beads",
        "source_bead_id": bead_id,
        "idempotency_key": bead_id,
        "title": f"{bead_id}: {packet.get('goal', '')}",
        "assignee": profile,
        "priority": bead.get("priority", 2),
        "mode": (bead.get("metadata", {}) or {}).get("hermes_mode", "pr"),
        "body": json.dumps(packet, indent=2),
    }


def build_dispatch_plan(
    ready_beads: Iterable[Any],
    backend: DispatchBackend | None = None,
    payload_builder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> list[DispatchOp]:
    """Build a pure dispatch operation plan from ready Beads issues.

    This function is the dry-run side of the dispatch contract. It
    performs *no* live mutation: ``backend`` is accepted only as a
    capability hint (so callers can verify a backend is wired up
    before they build a plan), and is never called by the planner.

    Parameters
    ----------
    ready_beads:
        Iterable of Beads issue dicts (typically the output of
        ``bd ready --json``). Each dict must contain an ``id`` field.
    backend:
        Optional backend capability hint. The planner never calls it;
        it is accepted so the apply step can receive a backend that
        the planner has at least *seen* during dry-run. Any object
        satisfies this signature — the planner does not type-check it.
    payload_builder:
        Optional pure mapping from bead dict to backend payload. The
        default is :func:`kanban_payload_for_bead`, which builds the
        IO-free Kanban-shaped payload used by unit tests. CLI callers
        may inject a richer builder that gathers handoff comments,
        preserving the existing dry-run wire format while keeping
        operation planning independent of Click and backends.

    Returns
    -------
    list[DispatchOp]
        One op per input bead, in input order. Each is a
        ``DispatchOpKind.CREATE`` with a Kanban-shaped payload, or a
        ``DispatchOpKind.SKIPPED`` with a human-readable reason.
    """
    # Touch the parameter so static analyzers know it's intentionally
    # accepted but unused for live mutation.
    _ = backend
    build_payload = payload_builder or kanban_payload_for_bead

    plan: list[DispatchOp] = []
    for bead in ready_beads:
        if not isinstance(bead, dict):
            plan.append(
                DispatchOp(
                    kind=DispatchOpKind.SKIPPED,
                    bead_id="",
                    reason=f"entry is not a dict: got {type(bead).__name__}",
                )
            )
            continue
        bead_id = str(bead.get("id", "") or "")
        if not bead_id:
            plan.append(
                DispatchOp(
                    kind=DispatchOpKind.SKIPPED,
                    bead_id="",
                    reason="bead is missing an id",
                )
            )
            continue
        payload = build_payload(bead)
        plan.append(DispatchOp(kind=DispatchOpKind.CREATE, bead_id=bead_id, payload=payload))
    return plan
