"""
hermes-beads dashboard plugin — backend API routes.

Mounted automatically by the Hermes dashboard at /api/plugins/hermes-beads/.

Endpoints:
  GET  /hello                             — health check
  GET  /api/projects                      — discover all Beads projects
  GET  /api/projects/<name>/beads         — list beads for a project
  GET  /api/projects/<name>/graph         — bead DAG data for vis-network
  POST /api/projects/<name>/dispatch      — dispatch selected beads
  POST /api/projects/<name>/gate/<id>     — resolve a blocking gate
  GET  /beads/<id>                        — single bead detail
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hermes_beads.bead_model import BeadStatus
from hermes_beads.bead_reader import discover_projects, read_project_beads
from hermes_beads.graph_builder import build_graph_raw

_log = logging.getLogger(__name__)
router = APIRouter()

# ── in-memory request cache ───────────────────────────────────────────

_cache: dict[str, tuple[float, object]] = {}
CACHE_TTL = 10  # seconds


def _cache_get(key: str):
    """Return cached value if fresh, otherwise None."""
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry[0]) < CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key: str, value: object):
    _cache[key] = (time.monotonic(), value)


def _cache_bust(prefix: str):
    """Remove all cache entries matching a prefix."""
    for k in list(_cache):
        if k.startswith(prefix):
            del _cache[k]


# ── request models ────────────────────────────────────────────────────


class DispatchRequest(BaseModel):
    bead_ids: list[str]


class GateResolveRequest(BaseModel):
    comment: str = ""


# ── helpers ───────────────────────────────────────────────────────────


def _find_project(project_name: str):
    """Look up a project by name, raise 404 if not found."""
    projects = discover_projects()
    project = next((p for p in projects if p.name == project_name), None)
    if not project:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' not found. Available: "
            f"{[p.name for p in projects]}",
        )
    return project


def _bd(*args: str, cwd: Optional[str] = None) -> dict | list:
    """Run a ``bd`` CLI command and return parsed JSON output."""
    cmd = ["bd", "--json"] + list(args)
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, cwd=cwd,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"bd exited with code {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout.strip()}


# ── project discovery ──────────────────────────────────────────────────


@router.get("/api/projects")
async def list_projects():
    """Discover all Beads projects on this machine."""
    cached = _cache_get("projects")
    if cached:
        return cached
    try:
        projects = discover_projects()
        data = {
            "projects": [p.model_dump() for p in projects],
            "count": len(projects),
        }
        _cache_set("projects", data)
        return data
    except Exception as exc:
        _log.exception("Failed to discover projects")
        raise HTTPException(status_code=500, detail=str(exc))


# ── beads for a project ────────────────────────────────────────────────


@router.get("/api/projects/{project_name}/beads")
async def list_project_beads(project_name: str):
    """Return all beads in a specific project, parsed from JSONL."""
    project = _find_project(project_name)
    beads = read_project_beads(project.path)
    return {
        "project": project_name,
        "path": project.path,
        "beads": [b.model_dump(exclude={"dependencies"}) for b in beads],
        "count": len(beads),
    }


# ── graph data for vis-network ─────────────────────────────────────────


@router.get("/api/projects/{project_name}/graph")
async def project_graph(project_name: str):
    """Return bead DAG data for vis-network rendering."""
    cache_key = f"graph:{project_name}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    project = _find_project(project_name)
    beads = read_project_beads(project.path)
    data = build_graph_raw(beads, project_name=project_name)
    _cache_set(cache_key, data)
    return data


# ── dispatch ──────────────────────────────────────────────────────────


@router.post("/api/projects/{project_name}/dispatch")
async def dispatch_beads(project_name: str, body: DispatchRequest):
    """Dispatch selected beads via ``hb bridge dispatch --apply``.

    Runs in the project directory so bd auto-discovers the workspace.
    """
    project = _find_project(project_name)

    if not body.bead_ids:
        raise HTTPException(status_code=400, detail="No bead_ids provided")

    # Check if hb CLI is available before attempting dispatch
    import shutil
    if not shutil.which("hb"):
        raise HTTPException(
            status_code=503,
            detail="hb CLI not found on PATH. Install hermes-beads to enable dispatch."
        )

    results = []
    for bid in body.bead_ids:
        try:
            # Use hb CLI if available, fall back to bd update --claim
            cmd = ["hb", "bridge", "dispatch", "--apply", "--bead", bid]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=project.path,
            )
            success = result.returncode == 0
            results.append({
                "bead_id": bid,
                "success": success,
                "output": (result.stdout + result.stderr).strip()[:500],
            })
        except Exception as exc:
            results.append({
                "bead_id": bid,
                "success": False,
                "output": str(exc),
            })

    dispatched = sum(1 for r in results if r["success"])
    if dispatched > 0:
        _cache_bust("graph:")  # bust all graph caches on state change
    return {
        "project": project_name,
        "dispatched": dispatched,
        "failed": sum(1 for r in results if not r["success"]),
        "results": results,
    }


# ── gate resolver ─────────────────────────────────────────────────────


@router.post("/api/projects/{project_name}/gate/{bead_id}")
async def resolve_gate(project_name: str, bead_id: str, body: GateResolveRequest):
    """Mark a bead's blocking dependency as resolved.

    Closes the specified bead via bd close. If the bead has open
    child tasks, adds a comment instead.
    """
    project = _find_project(project_name)

    try:
        bead_data = _bd("show", bead_id, cwd=project.path)
        if not isinstance(bead_data, dict):
            raise HTTPException(status_code=500, detail="Could not read bead data")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"bd show failed: {e}")

    try:
        _bd("close", bead_id, "-m", body.comment or "Resolved via dashboard", cwd=project.path)
        _cache_bust("graph:")  # bust graph caches on state change
        return {
            "bead_id": bead_id,
            "action": "closed",
            "message": f"Bead {bead_id} closed successfully",
        }
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"bd close failed: {e}")


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


@router.get("/api/projects/{project_name}/beads/{bead_id}")
async def show_bead(project_name: str, bead_id: str):
    """Show detail for a single bead via bd CLI, scoped to a project."""
    project = _find_project(project_name)
    try:
        data = _bd("show", bead_id, cwd=project.path)
        return {"bead_id": bead_id, "project": project_name, "bead": data}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
