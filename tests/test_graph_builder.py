"""Tests for graph_builder edge construction.

The graph must carry every dependency type, not just "blocks": in a mature
store "parent-child" (epic structure) is typically the most common type, and
dropping it hides the shape of the project.
"""
from __future__ import annotations

import pytest

from hermes_beads.bead_model import Bead, BeadDependency
from hermes_beads.graph_builder import build_graph, build_graph_raw, edge_style


def _bead(bead_id: str, deps: list[tuple[str, str]] | None = None) -> Bead:
    """Build a Bead with (depends_on_id, type) dependency tuples."""
    return Bead(
        id=bead_id,
        title=f"title for {bead_id}",
        dependencies=[
            BeadDependency(id=bead_id, depends_on_id=src, type=dep_type)
            for src, dep_type in (deps or [])
        ],
    )


@pytest.fixture
def mixed_beads() -> list[Bead]:
    """A tiny store exercising every relationship type plus a dangling ref."""
    return [
        _bead("p-1"),
        _bead("p-2", [("p-1", "blocks")]),
        _bead("p-3", [("p-1", "parent-child")]),
        _bead("p-4", [("p-2", "discovered-from")]),
        _bead("p-5", [("p-3", "related"), ("p-4", "supersedes")]),
        _bead("p-6", [("not-in-this-project", "blocks")]),
    ]


# ═══════════════════════════════════════════════════════════════════════
#  All dependency types are rendered
# ═══════════════════════════════════════════════════════════════════════


class TestEveryDependencyType:

    def test_build_graph_keeps_non_blocks_types(self, mixed_beads):
        graph = build_graph(mixed_beads, "proj")
        assert {e.dep_type for e in graph.edges} == {
            "blocks", "parent-child", "discovered-from", "related", "supersedes",
        }

    def test_build_graph_raw_keeps_non_blocks_types(self, mixed_beads):
        graph = build_graph_raw(mixed_beads, "proj")
        assert {e["type"] for e in graph["edges"]} == {
            "blocks", "parent-child", "discovered-from", "related", "supersedes",
        }

    def test_raw_reports_per_type_counts(self, mixed_beads):
        graph = build_graph_raw(mixed_beads, "proj")
        assert graph["edge_counts"] == {
            "blocks": 1, "parent-child": 1, "discovered-from": 1,
            "related": 1, "supersedes": 1,
        }

    def test_every_bead_becomes_a_node(self, mixed_beads):
        assert len(build_graph(mixed_beads, "proj").nodes) == len(mixed_beads)


# ═══════════════════════════════════════════════════════════════════════
#  Opt-in filtering preserves the old blocks-only view
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeTypeFilter:

    def test_blocks_only_filter(self, mixed_beads):
        graph = build_graph(mixed_beads, "proj", edge_types={"blocks"})
        assert [(e.from_, e.to) for e in graph.edges] == [("p-1", "p-2")]

    def test_filter_applies_to_raw(self, mixed_beads):
        graph = build_graph_raw(mixed_beads, "proj", edge_types={"parent-child"})
        assert [e["type"] for e in graph["edges"]] == ["parent-child"]

    def test_empty_filter_yields_no_edges(self, mixed_beads):
        assert build_graph(mixed_beads, "proj", edge_types=set()).edges == []


# ═══════════════════════════════════════════════════════════════════════
#  Dangling references and duplicates
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeHygiene:

    def test_dependency_on_unknown_bead_is_dropped(self, mixed_beads):
        """vis-network would materialise a phantom node for an unknown endpoint."""
        graph = build_graph(mixed_beads, "proj")
        assert all(e.from_ != "not-in-this-project" for e in graph.edges)

    def test_duplicate_dependency_is_deduplicated(self):
        beads = [_bead("p-1"), _bead("p-2", [("p-1", "blocks"), ("p-1", "blocks")])]
        assert len(build_graph(beads, "proj").edges) == 1

    def test_same_pair_with_two_types_yields_two_edges(self):
        beads = [_bead("p-1"), _bead("p-2", [("p-1", "blocks"), ("p-1", "related")])]
        assert len(build_graph(beads, "proj").edges) == 2

    def test_empty_depends_on_id_is_dropped(self):
        beads = [_bead("p-1"), _bead("p-2", [("", "blocks")])]
        assert build_graph(beads, "proj").edges == []


# ═══════════════════════════════════════════════════════════════════════
#  Styling
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeStyling:

    def test_each_known_type_has_a_distinct_colour(self):
        types = ["blocks", "parent-child", "discovered-from", "supersedes"]
        colours = {edge_style(t)["color"] for t in types}
        assert len(colours) == len(types)

    def test_unknown_type_falls_back_to_default_style(self):
        style = edge_style("some-future-type")
        assert style["color"] and "width" in style

    def test_raw_edge_carries_its_style(self, mixed_beads):
        graph = build_graph_raw(mixed_beads, "proj")
        parent = next(e for e in graph["edges"] if e["type"] == "parent-child")
        assert parent["color"]["color"] == edge_style("parent-child")["color"]
