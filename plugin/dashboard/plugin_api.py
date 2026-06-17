"""
hermes-beads dashboard plugin — backend API routes.

Mounted automatically by the Hermes dashboard at /api/plugins/hermes-beads/.

Endpoints:
  GET  /hello              — health check
  GET  /beads              — list all beads (via bd CLI)
  GET  /beads/ready        — list ready (unblocked) beads
  GET  /beads/<id>         — show single bead detail
  GET  /beads/graph        — bead DAG data for vis-network rendering
"""

from fastapi import APIRouter, HTTPException
import subprocess
import json
import os
from pathlib import Path

router = APIRouter()


def _bd(*args: str, cwd: str | None = None) -> dict | list:
    """Run a ``bd`` CLI command and return parsed JSON output."""
    workdir = cwd or os.getcwd()
    cmd = ["bd", "--json"] + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=workdir,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"bd exited with code {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout.strip()}


def _find_workspace() -> str | None:
    """Walk up from cwd to find a Beads workspace (.beads/ directory)."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / ".beads").is_dir():
            return str(parent)
    return None


@router.get("/hello")
async def hello():
    """Health check — confirm the plugin API is mounted."""
    return {
        "plugin": "hermes-beads",
        "version": "2.0.0-alpha.1",
        "status": "ok",
    }


@router.get("/beads")
async def list_beads():
    """Return all beads in the current workspace."""
    cwd = _find_workspace()
    if not cwd:
        raise HTTPException(status_code=404, detail="No Beads workspace found from current directory")

    try:
        data = _bd("ready", cwd=cwd)
        return {"workspace": cwd, "beads": data if isinstance(data, list) else []}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/beads/ready")
async def list_ready_beads():
    """Return only ready (unblocked) beads."""
    cwd = _find_workspace()
    if not cwd:
        raise HTTPException(status_code=404, detail="No Beads workspace found from current directory")

    try:
        raw = _bd("ready", cwd=cwd)
        if not isinstance(raw, list):
            return {"workspace": cwd, "beads": [], "count": 0}
        # Filter to only OPEN status beads (not blocked)
        ready = [b for b in raw if isinstance(b, dict) and b.get("status") == "OPEN"]
        return {"workspace": cwd, "beads": ready, "count": len(ready)}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/beads/{bead_id}")
async def show_bead(bead_id: str):
    """Show detail for a single bead."""
    cwd = _find_workspace()
    if not cwd:
        raise HTTPException(status_code=404, detail="No Beads workspace found from current directory")

    try:
        data = _bd("show", bead_id, cwd=cwd)
        return {"workspace": cwd, "bead": data}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/beads/graph")
async def bead_graph():
    """Return bead DAG data suitable for vis-network rendering.

    Builds nodes (beads) and edges (dependency relationships)
    from the Beads workspace.
    """
    cwd = _find_workspace()
    if not cwd:
        raise HTTPException(status_code=404, detail="No Beads workspace found from current directory")

    try:
        raw = _bd("ready", cwd=cwd)
        if not isinstance(raw, list):
            return {"workspace": cwd, "nodes": [], "edges": []}

        nodes = []
        edges = []
        seen = set()

        for bead in raw:
            if not isinstance(bead, dict):
                continue
            bid = bead.get("id", "unknown")
            if bid in seen:
                continue
            seen.add(bid)

            status = bead.get("status", "OPEN")
            title = bead.get("title", bid)
            priority = bead.get("priority", "")

            nodes.append({
                "id": bid,
                "label": bid,
                "title": title,
                "status": status,
                "priority": priority,
                "group": status.lower(),
            })

            # Dependency edges: blocked beads → their blockers
            blocks = bead.get("blocks", [])
            if isinstance(blocks, list):
                for blocker in blocks:
                    if isinstance(blocker, dict):
                        blocker_id = blocker.get("id", "")
                        if blocker_id:
                            edges.append({"from": blocker_id, "to": bid, "arrows": "to"})

        return {
            "workspace": cwd,
            "nodes": nodes,
            "edges": edges,
            "bead_count": len(nodes),
        }
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
