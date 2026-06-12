"""Tests for result operation IDs and comment marker parsing."""
from __future__ import annotations

import hashlib
import json
from hermes_beads.result_ops import (
    build_op_id,
    parse_op_marker,
    OpStatus,
)


class TestBuildOpId:
    """Stable operation IDs from bead_id, dispatch_id, status, and summary."""

    def test_same_inputs_produce_same_id(self) -> None:
        op1 = build_op_id("hb-abc", "task-123", OpStatus.COMPLETED, "summary here")
        op2 = build_op_id("hb-abc", "task-123", OpStatus.COMPLETED, "summary here")
        assert op1 == op2

    def test_different_bead_id_different_id(self) -> None:
        op1 = build_op_id("hb-abc", "task-123", OpStatus.COMPLETED, "same")
        op2 = build_op_id("hb-xyz", "task-123", OpStatus.COMPLETED, "same")
        assert op1 != op2

    def test_different_dispatch_id_different_id(self) -> None:
        op1 = build_op_id("hb-abc", "task-123", OpStatus.COMPLETED, "same")
        op2 = build_op_id("hb-abc", "task-456", OpStatus.COMPLETED, "same")
        assert op1 != op2

    def test_different_status_different_id(self) -> None:
        op1 = build_op_id("hb-abc", "task-123", OpStatus.COMPLETED, "same")
        op2 = build_op_id("hb-abc", "task-123", OpStatus.FAILED, "same")
        assert op1 != op2

    def test_different_summary_different_id(self) -> None:
        op1 = build_op_id("hb-abc", "task-123", OpStatus.COMPLETED, "foo")
        op2 = build_op_id("hb-abc", "task-123", OpStatus.COMPLETED, "bar")
        assert op1 != op2

    def test_id_contains_bead_id_prefix(self) -> None:
        op = build_op_id("hb-abc", "task-123", OpStatus.COMPLETED, "summary")
        assert "hb-abc" in op

    def test_id_is_deterministic_hex_string(self) -> None:
        """ID should be a short hex string (stable hash, not random UUID)."""
        op = build_op_id("hb-abc", "task-123", OpStatus.COMPLETED, "summary")
        # Should look like: hb-abc-a1b2c3d4
        assert all(c in "0123456789abcdef" for c in op.split("-")[-1])

    def test_empty_summary_produces_stable_id(self) -> None:
        op1 = build_op_id("hb-abc", "task-123", OpStatus.COMPLETED, "")
        op2 = build_op_id("hb-abc", "task-123", OpStatus.COMPLETED, "")
        assert op1 == op2

    def test_idempotent_called_multiple_times(self) -> None:
        """Calling build_op_id with same inputs N times produces same result."""
        args = ("hb-xyz", "task-999", OpStatus.FAILED, "test summary")
        results = [build_op_id(*args) for _ in range(5)]
        assert len(set(results)) == 1


class TestParseOpMarker:
    """Parse hermes-beads-op: <op_id> markers from comment text."""

    def test_parses_valid_marker(self) -> None:
        text = "hermes-beads-op: hb-abc-a1b2c3d4"
        assert parse_op_marker(text) == "hb-abc-a1b2c3d4"

    def test_parses_marker_with_surrounding_text(self) -> None:
        text = "Result: hermes-beads-op: hb-abc-a1b2c3d4 — synced"
        assert parse_op_marker(text) == "hb-abc-a1b2c3d4"

    def test_parses_marker_at_end_of_line(self) -> None:
        text = "Operation completed hermes-beads-op: hb-abc-a1b2c3d4"
        assert parse_op_marker(text) == "hb-abc-a1b2c3d4"

    def test_no_marker_returns_none(self) -> None:
        text = "Just a regular comment without any marker"
        assert parse_op_marker(text) is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_op_marker("") is None

    def test_malformed_marker_returns_none(self) -> None:
        """Marker keyword present but format is wrong."""
        assert parse_op_marker("hermes-beads-ops: hb-abc") is None
        assert parse_op_marker("hermes-beads-op:") is None
        assert parse_op_marker("hermes-beads-op: ") is None  # whitespace only

    def test_case_sensitive(self) -> None:
        """Marker detection is case-sensitive."""
        assert parse_op_marker("Hermes-Beads-Op: hb-abc") is None

    def test_whitespace_variations(self) -> None:
        text = "  hermes-beads-op:   hb-xyz-1234  "
        assert parse_op_marker(text) == "hb-xyz-1234"


class TestOpStatus:
    """OpStatus enum values used across result_ops."""

    def test_all_statuses_are_unique_strings(self) -> None:
        statuses = [s.value for s in OpStatus]
        assert len(statuses) == len(set(statuses))

    def test_status_values_are_sensible(self) -> None:
        assert OpStatus.COMPLETED.value == "completed"
        assert OpStatus.FAILED.value == "failed"
        assert OpStatus.SKIPPED.value == "skipped"