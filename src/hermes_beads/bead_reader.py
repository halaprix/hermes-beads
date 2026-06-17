"""
Beads data reader — discovers projects and parses .beads/issues.jsonl files.

Operates purely on disk (no bd CLI dependency) for fast dashboard reads.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from hermes_beads.bead_model import Bead, BeadDependency, BeadProject, BeadStatus, BeadPriority

# Known project locations to scan. Ordered: more specific first.
# Entries that contain a .beads/ directory themselves are treated as
# direct projects; entries that are parent directories are scanned
# for child projects (iterdir).
_SCAN_ROOTS = [
    Path.home() / "workspace",
    Path.home() / "leakwatch",
]

# Extra explicit paths that may not be under ~/workspace
_EXPLICIT_PROJECTS: list[Path] = []


def _extract_tags(bead: Bead) -> list[str]:
    """Extract tags from bead title/description for filtering."""
    tags = []
    # Extract priority tag
    if bead.priority.value:
        tags.append(bead.priority.value)
    # Extract type tag
    if bead.issue_type:
        tags.append(bead.issue_type)
    # Extract status tag
    tags.append(bead.status.value)
    return tags


def _parse_jsonl_line(line: str) -> Optional[Bead]:
    """Parse a single JSONL line into a Bead model. Returns None on failure."""
    try:
        raw = json.loads(line)
    except json.JSONDecodeError:
        return None

    if not isinstance(raw, dict):
        return None

    raw_id = raw.get("id", "")
    if not raw_id:
        return None

    # Parse dependencies
    deps = []
    raw_deps = raw.get("dependencies", [])
    if isinstance(raw_deps, list):
        for d in raw_deps:
            if isinstance(d, dict):
                deps.append(BeadDependency(
                    id=d.get("issue_id", d.get("id", "")),
                    depends_on_id=d.get("depends_on_id", ""),
                    type=d.get("type", "blocks"),
                ))

    # Parse timestamps
    created_at = None
    if raw.get("created_at"):
        try:
            created_at = datetime.fromisoformat(raw["created_at"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    updated_at = None
    if raw.get("updated_at"):
        try:
            updated_at = datetime.fromisoformat(raw["updated_at"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    # Map status string
    status_str = raw.get("status", "open").lower()
    try:
        status = BeadStatus(status_str)
    except ValueError:
        status = BeadStatus.OPEN

    # Map priority
    priority_str = raw.get("priority", "P1")
    if isinstance(priority_str, (int, float)):
        priority_str = f"P{int(priority_str)}"
    try:
        priority = BeadPriority(priority_str)
    except ValueError:
        priority = BeadPriority.P1

    bead = Bead(
        id=raw_id,
        title=raw.get("title", raw_id),
        description=raw.get("description", ""),
        status=status,
        priority=priority,
        type=raw.get("issue_type", "task"),
        assignee=raw.get("assignee", ""),
        owner=raw.get("owner", ""),
        estimated_minutes=raw.get("estimated_minutes", 0),
        created_at=created_at,
        updated_at=updated_at,
        created_by=raw.get("created_by", ""),
        dependencies=deps,
        dependency_count=len(deps),
        dependent_count=raw.get("dependent_count", 0),
        comment_count=raw.get("comment_count", 0),
    )

    bead.tags = _extract_tags(bead)
    return bead


def read_project_beads(project_path: str | Path) -> list[Bead]:
    """Parse a .beads/issues.jsonl file into a list of Bead objects.

    Args:
        project_path: Path to the project root (must contain .beads/ dir).

    Returns:
        List of Bead objects. Empty list if file missing or unparseable.
    """
    jsonl_path = Path(project_path) / ".beads" / "issues.jsonl"
    if not jsonl_path.is_file():
        return []

    beads: list[Bead] = []
    seen: set[str] = set()

    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                bead = _parse_jsonl_line(line)
                if bead and bead.id not in seen:
                    bead.project = str(Path(project_path).name)
                    beads.append(bead)
                    seen.add(bead.id)
    except (OSError, UnicodeDecodeError):
        pass

    return beads


def _register_project(
    projects: dict[str, BeadProject],
    entry: Path,
) -> None:
    """Register a single project directory in the projects map."""
    name = entry.name
    if name in projects:
        return
    beads = read_project_beads(entry)
    status_counts: dict[str, int] = {}
    for b in beads:
        s = b.status.value
        status_counts[s] = status_counts.get(s, 0) + 1
    projects[name] = BeadProject(
        name=name,
        path=str(entry.resolve()),
        bead_count=len(beads),
        status_counts=status_counts,
    )


def discover_projects() -> list[BeadProject]:
    """Scan known locations for Beads projects (.beads/issues.jsonl files).

    Two scanning strategies:
    1. Direct: if a scan root itself contains .beads/, register it.
    2. Iterdir: scan subdirectories of each root for .beads/.

    Returns:
        List of BeadProject objects with name, path, and bead counts.
    """
    projects: dict[str, BeadProject] = {}

    # Scan explicit paths first
    all_roots = [Path(p) for p in _EXPLICIT_PROJECTS if Path(p).is_dir()]
    all_roots.extend([p for p in _SCAN_ROOTS if p.is_dir()])

    for root in all_roots:
        # Strategy 1: check if the root itself is a bead project
        if (root / ".beads" / "issues.jsonl").is_file():
            _register_project(projects, root)

        # Strategy 2: scan subdirectories
        try:
            for entry in root.iterdir():
                if not entry.is_dir():
                    continue
                jsonl = entry / ".beads" / "issues.jsonl"
                if not jsonl.is_file():
                    continue
                _register_project(projects, entry)
        except PermissionError:
            pass

    return list(projects.values())
