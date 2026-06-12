"""Result operation IDs and comment marker parsing.

Provides stable operation IDs for the result-sync write path, enabling
exactly-once semantics when re-running sync operations.

An operation ID is derived from: bead_id + dispatch_id + status + summary_hash.
A comment marker parser extracts ``hermes-beads-op: <op_id>`` from comment text.
"""
from __future__ import annotations

import hashlib
import re
from enum import Enum


class OpStatus(Enum):
    """Result operation status values used in operation IDs."""

    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


def _summary_hash(summary: str) -> str:
    """Return first 8 hex chars of SHA-256 of *summary*."""
    return hashlib.sha256(summary.encode()).hexdigest()[:8]


def build_op_id(bead_id: str, dispatch_id: str, status: OpStatus, summary: str) -> str:
    """Build a stable, deterministic operation ID.

    Parameters
    ----------
    bead_id:
        The beads issue ID, e.g. ``"hb-abc"``.
    dispatch_id:
        The Hermes Kanban task/dispatch ID, e.g. ``"task-123"``.
    status:
        One of :class:`OpStatus`.
    summary:
        Free-text summary of the result (e.g. error message, output excerpt).

    Returns
    -------
    str
        A stable ID in the form ``{bead_id}-{last_8_hex_chars}``.
        The same inputs always produce the same ID.
    """
    h = _summary_hash(f"{bead_id}\n{dispatch_id}\n{status.value}\n{summary}")
    return f"{bead_id}-{h}"


# Regex for extracting "hermes-beads-op: <op_id>" from comment text.
# Matches the literal prefix followed by whitespace and the op_id token.
_OP_MARKER_RE = re.compile(r"hermes-beads-op:\s*(\S+)")


def parse_op_marker(text: str) -> str | None:
    """Extract an operation ID from a comment's ``hermes-beads-op:`` marker.

    Parameters
    ----------
    text:
        Raw comment text (may contain surrounding context).

    Returns
    -------
    str | None
        The operation ID if a valid marker is found, otherwise ``None``.
    """
    m = _OP_MARKER_RE.search(text)
    if m is None:
        return None
    op_id = m.group(1).strip()
    # Reject empty or whitespace-only
    if not op_id:
        return None
    return op_id