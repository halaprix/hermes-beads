"""
Bead graph builder — produces vis-network-compatible {nodes, edges} dicts.

Consumes lists of Bead objects from bead_reader and emits the JSON shape
the dashboard frontend expects for rendering interactive DAGs.
"""
from __future__ import annotations

from typing import Container, Optional

from hermes_beads.bead_model import (
    Bead,
    BeadEdge,
    BeadGraph,
    BeadNode,
    BeadPriority,
    BeadStatus,
)

# ── vis-network node colours ──────────────────────────────────────────

_NODE_COLORS: dict[BeadStatus, dict[str, str]] = {
    BeadStatus.OPEN: {
        "background": "#00ff88",
        "border": "#00cc66",
        "highlight": {"background": "#33ff99", "border": "#00ff88"},
    },
    BeadStatus.IN_PROGRESS: {
        "background": "#ffaa00",
        "border": "#cc8800",
        "highlight": {"background": "#ffbb33", "border": "#ffaa00"},
    },
    BeadStatus.BLOCKED: {
        "background": "#ff4477",
        "border": "#cc3355",
        "highlight": {"background": "#ff6688", "border": "#ff4477"},
    },
    BeadStatus.CLOSED: {
        "background": "#666666",
        "border": "#444444",
        "highlight": {"background": "#888888", "border": "#666666"},
    },
    BeadStatus.DEFERRED: {
        "background": "#888888",
        "border": "#666666",
        "highlight": {"background": "#aaaaaa", "border": "#888888"},
    },
}

_NODE_SHAPES: dict[BeadStatus, str] = {
    BeadStatus.OPEN: "dot",
    BeadStatus.IN_PROGRESS: "dot",
    BeadStatus.BLOCKED: "dot",
    BeadStatus.CLOSED: "dot",
    BeadStatus.DEFERRED: "dot",
}

# Size scales by priority: P0=largest, P4=smallest
_PRIORITY_SIZE: dict[BeadPriority, int] = {
    BeadPriority.P0: 28,
    BeadPriority.P1: 22,
    BeadPriority.P2: 18,
    BeadPriority.P3: 14,
    BeadPriority.P4: 12,
}


def _node_for_bead(bead: Bead) -> dict:
    """Build a vis-network node dict from a Bead."""
    colors = _NODE_COLORS.get(bead.status, _NODE_COLORS[BeadStatus.CLOSED])
    size = _PRIORITY_SIZE.get(bead.priority, 16)
    is_closed = bead.status in (BeadStatus.CLOSED, BeadStatus.DEFERRED)

    return {
        "id": bead.id,
        "label": bead.id,
        "title": (
            f"<b>{bead.id}</b><br>"
            f"{bead.title or bead.id}<br>"
            f"<i>{bead.status.value} · {bead.priority.value}</i>"
        ),
        "group": bead.status.value,
        "color": colors,
        "shape": _NODE_SHAPES.get(bead.status, "dot"),
        "size": size,
        "font": {
            "size": 11,
            "color": "#888888" if is_closed else "#ffffff",
            "face": "monospace",
        },
        "borderWidth": 2 if not is_closed else 1,
        "shadow": {
            "enabled": not is_closed,
            "size": 10,
            "color": colors.get("background", "#666"),
        },
    }


# ── dependency-type edge styling ──────────────────────────────────────
#
# Beads models several relationship kinds. "blocks" is the execution
# constraint, but "parent-child" carries the epic structure and is usually
# the most common type in a mature store — rendering only "blocks" hides
# the shape of the project. Each type gets its own colour/dash so the graph
# stays readable with all of them switched on.

_EDGE_STYLES: dict[str, dict] = {
    "blocks": {"color": "#ff6688", "dashes": False, "width": 1.6},
    "parent-child": {"color": "#4a7fd4", "dashes": False, "width": 1.1},
    "discovered-from": {"color": "#7a5cbf", "dashes": [4, 3], "width": 1.0},
    "related": {"color": "#4a8f8f", "dashes": [2, 3], "width": 0.9},
    "relates-to": {"color": "#4a8f8f", "dashes": [2, 3], "width": 0.9},
    "supersedes": {"color": "#bf8f3c", "dashes": [6, 3], "width": 1.2},
}
_DEFAULT_EDGE_STYLE = {"color": "#444466", "dashes": False, "width": 1.0}


def edge_style(dep_type: str) -> dict:
    """Return the vis-network styling for a dependency type."""
    return _EDGE_STYLES.get(dep_type, _DEFAULT_EDGE_STYLE)


def _edge_for_dep(bead: Bead, dep_id: str, dep_type: str = "blocks") -> dict:
    """Build a vis-network edge dict from a dependency."""
    style = edge_style(dep_type)
    return {
        "from": dep_id,
        "to": bead.id,
        "arrows": "to",
        "type": dep_type,
        "color": {"color": style["color"], "highlight": "#8888aa"},
        "dashes": style["dashes"],
        "smooth": {"type": "curvedCW", "roundness": 0.2},
        "width": style["width"],
    }


def _iter_edges(beads: list[Bead], edge_types: Optional[Container[str]]):
    """Yield (dep_type, source_id, target_bead) for every dependency to draw.

    Drops dependencies whose source is not itself in ``beads`` — vis-network
    materialises a phantom node for an unknown edge endpoint, so a reference
    to a bead outside this project would otherwise appear as a ghost.
    Deduplicates on (source, target, type).
    """
    known = {b.id for b in beads}
    seen: set[tuple[str, str, str]] = set()

    for bead in beads:
        for dep in bead.dependencies:
            src = dep.depends_on_id
            if not src or src not in known:
                continue
            if edge_types is not None and dep.type not in edge_types:
                continue
            key = (src, bead.id, dep.type)
            if key in seen:
                continue
            seen.add(key)
            yield dep.type, src, bead


def build_graph(
    beads: list[Bead],
    project_name: str = "",
    edge_types: Optional[Container[str]] = None,
) -> BeadGraph:
    """Build a full BeadGraph from a list of Bead objects.

    Args:
        beads: Parsed beads from bead_reader.read_project_beads().
        project_name: Optional project name for metadata.
        edge_types: Optional allowlist of dependency types to render.
            ``None`` (default) renders every type. Pass ``{"blocks"}`` for
            the execution-constraint-only view.

    Returns:
        BeadGraph with nodes and edges in vis-network format.
    """
    nodes = []
    seen_nodes: set[str] = set()

    for bead in beads:
        if bead.id not in seen_nodes:
            nodes.append(BeadNode(
                id=bead.id,
                label=bead.id,
                title=bead.title or bead.id,
                status=bead.status,
                priority=bead.priority,
                group=bead.status.value,
            ))
            seen_nodes.add(bead.id)

    edges = [
        BeadEdge.model_validate({
            "from": src,
            "to": bead.id,
            "arrows": "to",
            "type": dep_type,
        })
        for dep_type, src, bead in _iter_edges(beads, edge_types)
    ]

    return BeadGraph(
        project=project_name,
        nodes=nodes,
        edges=edges,
    )


def build_graph_raw(
    beads: list[Bead],
    project_name: str = "",
    edge_types: Optional[Container[str]] = None,
) -> dict:
    """Like build_graph() but returns raw vis-network dicts (not Pydantic).

    This is the format the frontend expects: nodes have colour, shadow,
    size, and shape fields; edges have smooth curve config.

    ``edge_types`` behaves as in :func:`build_graph`. ``edge_counts`` in the
    result lets the frontend build per-type filter chips without a second
    pass over the graph.
    """
    nodes = []
    seen_nodes: set[str] = set()

    for bead in beads:
        if bead.id not in seen_nodes:
            nodes.append(_node_for_bead(bead))
            seen_nodes.add(bead.id)

    edges = []
    edge_counts: dict[str, int] = {}
    for dep_type, src, bead in _iter_edges(beads, edge_types):
        edges.append(_edge_for_dep(bead, src, dep_type))
        edge_counts[dep_type] = edge_counts.get(dep_type, 0) + 1

    return {
        "project": project_name,
        "nodes": nodes,
        "edges": edges,
        "bead_count": len(nodes),
        "edge_counts": edge_counts,
    }
