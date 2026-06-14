"""Human approval gate helpers for hermes-beads.

Gates are represented as public Beads metadata. These helpers only plan and
explain gate operations; mutating commands remain explicit and dry-run first.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

REVIEW_LABELS = {"review", "requires-review", "pr-gated", "reviewer"}
GATE_STATUS_PENDING = "pending"
GATE_STATUS_APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class GateRecord:
    """A public-safe approval gate record derived from Beads metadata."""

    bead_id: str
    title: str
    gate_type: str
    status: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serializable gate record."""
        return {
            "bead_id": self.bead_id,
            "title": self.title,
            "gate_type": self.gate_type,
            "status": self.status,
            "reason": self.reason,
        }


def _truthy(value: Any) -> bool:
    """Return whether a metadata value should be treated as true."""
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "required", "pending"}


def bead_requires_review(bead: dict[str, Any]) -> bool:
    """Return whether a bead should route through a reviewer profile."""
    metadata = bead.get("metadata", {}) or {}
    labels = set(bead.get("labels", []) or [])
    return _truthy(metadata.get("hermes_requires_review")) or bool(labels & REVIEW_LABELS)


def gate_for_bead(bead: dict[str, Any]) -> GateRecord | None:
    """Return a gate record for a bead when gate metadata requests one."""
    metadata = bead.get("metadata", {}) or {}
    status = str(metadata.get("hermes_gate_status", "") or "")
    required = _truthy(metadata.get("hermes_requires_approval")) or status == GATE_STATUS_PENDING
    if not required:
        return None
    return GateRecord(
        bead_id=str(bead.get("id", "")),
        title=str(bead.get("title", "")),
        gate_type=str(metadata.get("hermes_gate_type", "human-approval") or "human-approval"),
        status=status or GATE_STATUS_PENDING,
        reason=str(metadata.get("hermes_gate_reason", "") or ""),
    )


def list_gates(beads: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    """List pending/declared approval gates from bead dictionaries."""
    records = []
    for bead in beads:
        record = gate_for_bead(bead)
        if record is not None:
            records.append(record.to_dict())
    return records


def build_gate_approval_plan(bead: dict[str, Any]) -> dict[str, Any]:
    """Build the dry-run mutation plan for approving a gate."""
    record = gate_for_bead(bead)
    if record is None:
        return {"op": "skipped", "bead_id": str(bead.get("id", "")), "reason": "no pending gate"}
    if record.status == GATE_STATUS_APPROVED:
        return {"op": "skipped", "bead_id": record.bead_id, "reason": "gate already approved"}
    return {
        "op": "approve-gate",
        "bead_id": record.bead_id,
        "metadata": {
            "hermes_gate_status": GATE_STATUS_APPROVED,
            "hermes_requires_approval": "false",
        },
    }


def escalation_metadata(iteration: int, threshold: int) -> dict[str, str]:
    """Return metadata for retry escalation when threshold is reached."""
    if iteration < threshold:
        return {}
    return {
        "hermes_gate_status": GATE_STATUS_PENDING,
        "hermes_gate_type": "retry-escalation",
        "hermes_requires_approval": "true",
        "hermes_gate_reason": f"retry threshold reached: {iteration}",
    }
