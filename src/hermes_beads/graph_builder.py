"""
Bead graph builder — produces vis-network-compatible {nodes, edges} dicts.

Consumes lists of Bead objects from bead_reader and emits the JSON shape
the dashboard frontend expects for rendering interactive DAGs.
"""
from __future__ import annotations

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


def _edge_for_dep(bead: Bead, dep_id: str) -> dict:
    """Build a vis-network edge dict from a dependency."""
    return {
        "from": dep_id,
        "to": bead.id,
        "arrows": "to",
        "color": {"color": "#444466", "highlight": "#8888aa"},
        "smooth": {"type": "curvedCW", "roundness": 0.2},
        "width": 1,
    }


def build_graph(beads: list[Bead], project_name: str = "") -> BeadGraph:
    """Build a full BeadGraph from a list of Bead objects.

    Args:
        beads: Parsed beads from bead_reader.read_project_beads().
        project_name: Optional project name for metadata.

    Returns:
        BeadGraph with nodes and edges in vis-network format.
    """
    nodes = []
    edges = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str]] = set()

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

        for dep in bead.dependencies:
            edge_key = (dep.depends_on_id, bead.id)
            if dep.type == "blocks" and dep.depends_on_id and edge_key not in seen_edges:
                edges.append(BeadEdge.model_validate({
                    "from": dep.depends_on_id,
                    "to": bead.id,
                    "arrows": "to",
                }))
                seen_edges.add(edge_key)

    return BeadGraph(
        project=project_name,
        nodes=nodes,
        edges=edges,
    )


def build_graph_raw(beads: list[Bead], project_name: str = "") -> dict:
    """Like build_graph() but returns raw vis-network dicts (not Pydantic).

    This is the format the frontend expects: nodes have colour, shadow,
    size, and shape fields; edges have smooth curve config.
    """
    nodes = []
    edges = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str]] = set()

    for bead in beads:
        if bead.id not in seen_nodes:
            nodes.append(_node_for_bead(bead))
            seen_nodes.add(bead.id)

        for dep in bead.dependencies:
            edge_key = (dep.depends_on_id, bead.id)
            if dep.type == "blocks" and dep.depends_on_id and edge_key not in seen_edges:
                edges.append(_edge_for_dep(bead, dep.depends_on_id))
                seen_edges.add(edge_key)

    return {
        "project": project_name,
        "nodes": nodes,
        "edges": edges,
        "bead_count": len(nodes),
    }
