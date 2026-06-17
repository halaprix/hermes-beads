"""
hermes-beads dashboard plugin — backend API routes.

Mounted automatically by the Hermes dashboard at /api/plugins/hermes-beads/.

Endpoints:
  GET  /hello                         — health check
  GET  /api/projects                  — discover all Beads projects
  GET  /api/projects/<name>/beads     — list beads for a project
  GET  /api/projects/<name>/graph     — bead DAG data for vis-network
  GET  /beads/<id>                    — single bead detail (via bd CLI)
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException

from hermes_beads.bead_model import BeadNode, BeadEdge, BeadGraph, BeadStatus
from hermes_beads.bead_reader import discover_projects, read_project_beads

_log = logging.getLogger(__name__)
router = APIRouter()

# ── project discovery ──────────────────────────────────────────────────


@router.get("/api/projects")
async def list_projects():
    """Discover all Beads projects on this machine.

    Returns a list of projects with their name, path, and bead counts.
    """
    try:
        projects = discover_projects()
        return {
            "projects": [p.model_dump() for p in projects],
            "count": len(projects),
        }
    except Exception as exc:
        _log.exception("Failed to discover projects")
        raise HTTPException(status_code=500, detail=str(exc))


# ── beads for a project ────────────────────────────────────────────────


@router.get("/api/projects/{project_name}/beads")
async def list_project_beads(project_name: str):
    """Return all beads in a specific project, parsed from JSONL.

    Falls back gracefully if the project is not found.
    """
    projects = discover_projects()
    project = next((p for p in projects if p.name == project_name), None)
    if not project:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' not found. Available: "
            f"{[p.name for p in projects]}",
        )

    beads = read_project_beads(project.path)
    return {
        "project": project_name,
        "path": project.path,
        "beads": [b.model_dump(exclude={"dependencies"}) for b in beads],
        "count": len(beads),
    }


# ── graph data for vis-network ─────────────────────────────────────────

_STATUS_COLORS = {
    BeadStatus.OPEN: "#00ff88",
    BeadStatus.IN_PROGRESS: "#ffaa00",
    BeadStatus.BLOCKED: "#ff4477",
    BeadStatus.CLOSED: "#666666",
    BeadStatus.DEFERRED: "#888888",
}


@router.get("/api/projects/{project_name}/graph")
async def project_graph(project_name: str):
    """Return bead DAG data for vis-network rendering.

    Builds nodes and edges from the project's beads, with colour
    coding by status and edges representing dependency relationships.
    """
    projects = discover_projects()
    project = next((p for p in projects if p.name == project_name), None)
    if not project:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' not found",
        )

    beads = read_project_beads(project.path)
    nodes = []
    edges = []

    for bead in beads:
        color = _STATUS_COLORS.get(bead.status, "#aaaaaa")
        nodes.append(BeadNode(
            id=bead.id,
            label=bead.id,
            title=bead.title or bead.id,
            status=bead.status,
            priority=bead.priority,
            group=bead.status.value,
        ).model_dump())

        # Dependency edges: beads that block this one
        for dep in bead.dependencies:
            if dep.type == "blocks" and dep.depends_on_id:
                edges.append(BeadEdge(
                    from_=dep.depends_on_id,
                    to=bead.id,
                    arrows="to",
                ).model_dump(by_alias=True))

    return {
        "project": project_name,
        "nodes": nodes,
        "edges": edges,
        "bead_count": len(nodes),
    }


# ── health check ───────────────────────────────────────────────────────


@router.get("/hello")
async def hello():
    """Health check — confirm the plugin API is mounted."""
    from importlib.metadata import version as pkg_version

    try:
        ver = pkg_version("hermes-beads")
    except Exception:
        ver = "2.0.0-alpha.1"

    return {
        "plugin": "hermes-beads",
        "version": ver,
        "status": "ok",
    }


# ── single bead detail (bd CLI fallback) ───────────────────────────────


def _bd(*args: str) -> dict | list:
    """Minimal bd CLI wrapper for single-bead lookups."""
    cmd = ["bd", "--json"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"bd exited with code {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout.strip()}


@router.get("/beads/{bead_id}")
async def show_bead(bead_id: str):
    """Show detail for a single bead via bd CLI."""
    try:
        data = _bd("show", bead_id)
        return {"bead_id": bead_id, "bead": data}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
