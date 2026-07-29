"""
Beads data reader — discovers projects and parses .beads/issues.jsonl files.

Operates purely on disk (no bd CLI dependency) for fast dashboard reads.

Project discovery is configurable via three mechanisms (first wins):
  1. ``HERMES_BEADS_PROJECT_DIRS`` env var — colon-separated paths
  2. ``~/.config/hermes-beads/projects.json`` — ``{"scan_roots": [...]}``
  3. Default: ``~/workspace``

Users who keep Beads projects outside ``~/workspace`` can set the env var
or write a small config file — no need to edit plugin source.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from hermes_beads.bead_model import Bead, BeadDependency, BeadProject, BeadStatus, BeadPriority

# Upper bound for a single ``bd export`` call. Generous: a cold Dolt start on a
# few-hundred-bead store is ~1s, and discovery may hit several projects.
_BD_TIMEOUT_SECONDS = 30


# ═══════════════════════════════════════════════════════════════════════
#  Config resolution
# ═══════════════════════════════════════════════════════════════════════

def _load_scan_roots() -> list[Path]:
    """Resolve scan roots in priority order: env var > config file > default.

    Returns a list of absolute ``Path`` objects.  Directories that do not
    exist on disk are silently dropped so a config shared across machines
    doesn't break.
    """
    # 1. Environment variable (highest priority)
    env_val = os.getenv("HERMES_BEADS_PROJECT_DIRS", "").strip()
    if env_val:
        return _expand_paths(env_val.split(":"))

    # 2. Config file
    config_path = Path.home() / ".config" / "hermes-beads" / "projects.json"
    try:
        if config_path.is_file():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "scan_roots" in data:
                roots = data["scan_roots"]
                if isinstance(roots, list):
                    return _expand_paths(roots)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        pass

    # 3. Default: ~/workspace (standard Beads convention)
    return _expand_paths(["~/workspace"])


def _expand_paths(paths: list[str]) -> list[Path]:
    """Expand user prefixes and drop non-existent directories."""
    resolved: list[Path] = []
    for raw in paths:
        raw = raw.strip()
        if not raw:
            continue
        p = Path(raw).expanduser().resolve()
        if p.is_dir():
            resolved.append(p)
    return resolved


# ═══════════════════════════════════════════════════════════════════════
#  Tag extraction
# ═══════════════════════════════════════════════════════════════════════


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


def _read_jsonl_file(jsonl_path: Path) -> Optional[list[str]]:
    """Return the lines of an on-disk JSONL export, or None if unreadable."""
    if not jsonl_path.is_file():
        return None
    try:
        return jsonl_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None


def _read_via_bd(project_path: Path) -> Optional[list[str]]:
    """Return JSONL lines by shelling out to ``bd export``, or None on failure.

    Beads switched its storage to Dolt: ``.beads/issues.jsonl`` is no longer
    written unless the workspace opts in via ``export.auto`` in
    ``.beads/config.yaml``. ``bd -C <dir> export`` streams the same records to
    stdout from any cwd, so a Dolt-only workspace stays readable.

    Memories are deliberately not requested: plain ``bd export`` omits them,
    and they can hold sensitive agent context that has no place in a graph.
    """
    if not (project_path / ".beads").is_dir():
        return None
    bd = shutil.which("bd") or shutil.which("beads")
    if bd is None:
        return None
    try:
        proc = subprocess.run(
            [bd, "-C", str(project_path), "export"],
            capture_output=True,
            text=True,
            timeout=_BD_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.splitlines()


def read_project_beads(project_path: str | Path) -> list[Bead]:
    """Read a project's beads into a list of Bead objects.

    Prefers ``.beads/issues.jsonl`` when present (no subprocess, fastest),
    and otherwise falls back to the ``bd`` CLI so Dolt-backed workspaces —
    the default since Beads moved off JSONL — are readable too.

    Args:
        project_path: Path to the project root (must contain .beads/ dir).

    Returns:
        List of Bead objects. Empty list if the project cannot be read.
    """
    project_path = Path(project_path)
    lines = _read_jsonl_file(project_path / ".beads" / "issues.jsonl")
    if lines is None:
        lines = _read_via_bd(project_path)
    if lines is None:
        return []

    beads: list[Bead] = []
    seen: set[str] = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        bead = _parse_jsonl_line(line)
        if bead and bead.id not in seen:
            bead.project = project_path.name
            beads.append(bead)
            seen.add(bead.id)

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


def discover_projects(scan_roots: Optional[list[Path]] = None) -> list[BeadProject]:
    """Scan for Beads projects (directories containing ``.beads/``).

    Two scanning strategies:
    1. **Direct**: if a scan root itself contains ``.beads/``, register it.
    2. **Iterdir**: scan subdirectories of each root for ``.beads/``.

    A workspace qualifies on the ``.beads/`` directory alone — requiring
    ``issues.jsonl`` would skip every Dolt-backed workspace, which is the
    default in current Beads.

    Args:
        scan_roots: Optional override list of directories to scan.  When
            ``None`` (default), roots are resolved via env var / config file
            / ``~/workspace`` fallback (see ``_load_scan_roots``).

    Returns:
        List of BeadProject objects with name, path, and bead counts.
    """
    if scan_roots is None:
        scan_roots = _load_scan_roots()

    projects: dict[str, BeadProject] = {}

    for root in scan_roots:
        # Strategy 1: check if the root itself is a bead project
        if (root / ".beads").is_dir():
            _register_project(projects, root)

        # Strategy 2: scan subdirectories
        try:
            for entry in root.iterdir():
                if not entry.is_dir():
                    continue
                if not (entry / ".beads").is_dir():
                    continue
                _register_project(projects, entry)
        except PermissionError:
            pass

    return list(projects.values())
