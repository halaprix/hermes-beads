"""Tests for approval gate helpers."""

from __future__ import annotations

from hermes_beads.gates import build_gate_approval_plan, escalation_metadata, list_gates


def test_list_gates_returns_pending_gate_shape() -> None:
    gates = list_gates(
        [
            {
                "id": "hb-gate",
                "title": "Needs approval",
                "metadata": {
                    "hermes_requires_approval": "true",
                    "hermes_gate_type": "human-approval",
                    "hermes_gate_status": "pending",
                    "hermes_gate_reason": "release",
                },
            }
        ]
    )
    assert gates == [
        {
            "bead_id": "hb-gate",
            "title": "Needs approval",
            "gate_type": "human-approval",
            "status": "pending",
            "reason": "release",
        }
    ]


def test_gate_approval_plan_for_invalid_gate_skips() -> None:
    assert build_gate_approval_plan({"id": "hb-open", "metadata": {}}) == {
        "op": "skipped",
        "bead_id": "hb-open",
        "reason": "no pending gate",
    }


def test_gate_approval_plan_is_dry_run_metadata_update() -> None:
    plan = build_gate_approval_plan(
        {"id": "hb-gate", "title": "Needs approval", "metadata": {"hermes_gate_status": "pending"}}
    )
    assert plan == {
        "op": "approve-gate",
        "bead_id": "hb-gate",
        "metadata": {"hermes_gate_status": "approved", "hermes_requires_approval": "false"},
    }


def test_retry_escalation_at_n_minus_one_does_not_escalate() -> None:
    assert escalation_metadata(2, 3) == {}


def test_retry_escalation_at_threshold_once_metadata() -> None:
    assert escalation_metadata(3, 3) == {
        "hermes_gate_status": "pending",
        "hermes_gate_type": "retry-escalation",
        "hermes_requires_approval": "true",
        "hermes_gate_reason": "retry threshold reached: 3",
    }
