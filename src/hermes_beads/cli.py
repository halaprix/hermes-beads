"""CLI for hermes-beads.

All bridge commands are dry-run-first. Commands that would mutate Hermes or
Beads state require explicit non-dry-run support before they can run live.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import click


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def get_version() -> str:
    """Read version from VERSION file at repo root."""
    return (REPO_ROOT / "VERSION").read_text().strip()


def _json_env(name: str) -> Any | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    return json.loads(raw)


def run_bd_json(args: list[str]) -> Any:
    """Run bd with JSON output and return parsed data."""
    result = subprocess.run(
        ["bd", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout or "null")


def run_bd_text(args: list[str]) -> str:
    """Run bd and return stdout as text."""
    result = subprocess.run(
        ["bd", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def get_bead_json(bead_id: str) -> dict[str, Any] | None:
    """Get bead data via bd show --json."""
    mock_data = _json_env("HB_MOCK_BD_SHOW_JSON")
    if mock_data is not None:
        beads = mock_data
    else:
        try:
            beads = run_bd_json(["show", bead_id, "--json"])
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return None

    if isinstance(beads, dict):
        beads = [beads]
    for bead in beads or []:
        if bead.get("id") == bead_id:
            return bead
    return None


def get_ready_beads() -> list[dict[str, Any]]:
    """Get ready beads via bd ready --json."""
    mock_data = _json_env("HB_MOCK_BD_READY_JSON")
    if mock_data is not None:
        return list(mock_data)
    try:
        data = run_bd_json(["ready", "--json"])
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return []
    return list(data or [])


def normalize_comments(raw: Any) -> list[dict[str, str]]:
    """Normalize bd comment output into the handoff packet shape."""
    if raw is None:
        return []
    if isinstance(raw, dict):
        raw_comments = raw.get("comments", [])
    else:
        raw_comments = raw
    comments: list[dict[str, str]] = []
    for item in raw_comments or []:
        if not isinstance(item, dict):
            continue
        body = item.get("body") or item.get("text") or item.get("comment") or item.get("content") or ""
        if not body:
            continue
        comments.append(
            {
                "author": str(item.get("author") or item.get("created_by") or item.get("actor") or ""),
                "body": str(body),
                "created_at": str(item.get("created_at") or item.get("timestamp") or ""),
            }
        )
    return comments


def get_comments(bead_id: str, bead: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Fetch comments for a bead, falling back to embedded bd show fields."""
    mock_data = _json_env("HB_MOCK_BD_COMMENTS_JSON")
    if mock_data is not None:
        return normalize_comments(mock_data)

    # Some bd show JSON versions may embed comments directly.
    embedded = normalize_comments((bead or {}).get("comments"))
    if embedded:
        return embedded

    try:
        return normalize_comments(run_bd_json(["comments", bead_id, "--json"]))
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return []


def _dependency_summary(bead: dict[str, Any]) -> list[dict[str, str]]:
    dependencies = []
    for dep in bead.get("dependencies", []):
        dependencies.append(
            {
                "id": str(dep.get("id", "")),
                "title": str(dep.get("title", "")),
                "status": str(dep.get("status", "")),
            }
        )
    return dependencies


def build_handoff_packet(bead: dict[str, Any]) -> dict[str, Any]:
    """Build a handoff packet from bead data."""
    metadata = bead.get("metadata", {}) or {}
    bead_id = str(bead.get("id", ""))
    return {
        "bead_id": bead_id,
        "goal": bead.get("title", ""),
        "description": bead.get("description", ""),
        "stop_condition": metadata.get("hermes_stop_condition", ""),
        "hermes_profile": metadata.get("hermes_profile", ""),
        "hermes_mode": metadata.get("hermes_mode", ""),
        "dependencies": _dependency_summary(bead),
        "comments": get_comments(bead_id, bead),
        "iteration": int(metadata.get("hermes_iteration", 0) or 0),
    }


def select_profile(bead: dict[str, Any]) -> str:
    """Choose the Hermes profile for a bead without embedding policy in Beads."""
    metadata = bead.get("metadata", {}) or {}
    explicit = metadata.get("hermes_profile")
    if explicit:
        return str(explicit)

    labels = set(bead.get("labels", []) or [])
    issue_type = bead.get("issue_type", "")
    if "docs" in labels or issue_type == "task" and "architecture" in labels:
        return "docs"
    if "planning" in labels or "architecture" in labels:
        return "planner"
    return "ts-dev"


def build_kanban_payload(bead: dict[str, Any]) -> dict[str, Any]:
    """Map a ready bead to a Hermes Kanban task payload."""
    packet = build_handoff_packet(bead)
    bead_id = packet["bead_id"]
    profile = select_profile(bead)
    return {
        "source": "beads",
        "source_bead_id": bead_id,
        "title": f"{bead_id}: {packet['goal']}",
        "assignee": profile,
        "priority": bead.get("priority", 2),
        "mode": (bead.get("metadata", {}) or {}).get("hermes_mode", "pr"),
        "body": json.dumps(packet, indent=2),
    }


def next_iteration(bead: dict[str, Any]) -> int:
    """Return the next retry iteration for a failed/timeout bead."""
    metadata = bead.get("metadata", {}) or {}
    return int(metadata.get("hermes_iteration", 0) or 0) + 1


def build_result_sync_operations(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map Hermes Kanban result records into dry-run bd operations."""
    operations: list[dict[str, Any]] = []
    for result in results:
        bead_id = result.get("bead_id") or result.get("source_bead_id")
        if not bead_id:
            continue
        status = result.get("status", "")
        summary = result.get("summary", "")
        if status in {"completed", "success", "done"}:
            operations.append({"op": "comment", "bead_id": bead_id, "body": f"result: {summary}"})
            operations.append({"op": "close", "bead_id": bead_id, "reason": "kanban task completed"})
        elif status in {"failed", "timeout", "error"}:
            bead = get_bead_json(str(bead_id)) or {"id": bead_id, "metadata": {}}
            operations.append({"op": "comment", "bead_id": bead_id, "body": f"failed: {summary}"})
            operations.append(
                {
                    "op": "update-metadata",
                    "bead_id": bead_id,
                    "metadata": {"hermes_status": "failed", "hermes_iteration": next_iteration(bead)},
                }
            )
    return operations


@click.group()
@click.version_option(version=get_version())
def main() -> None:
    """hermes-beads CLI — durable Beads state for disposable Hermes agents."""


@main.command()
@click.option("--dry-run", is_flag=True, help="Dry-run mode (no side effects)")
def ready(dry_run: bool) -> None:
    """Print handoff packet for the next ready bead."""
    if not dry_run:
        click.echo("Error: only --dry-run mode is supported", err=True)
        sys.exit(1)

    ready_beads = get_ready_beads()
    if not ready_beads:
        click.echo("Error: no ready beads found", err=True)
        sys.exit(1)

    click.echo(json.dumps(build_handoff_packet(ready_beads[0]), indent=2))


@main.command()
@click.argument("bead_id")
@click.option("--dry-run", is_flag=True, help="Dry-run mode (no side effects)")
def handoff(bead_id: str, dry_run: bool) -> None:
    """Print handoff packet for the specified bead."""
    if not dry_run:
        click.echo("Error: only --dry-run mode is supported", err=True)
        sys.exit(1)

    bead = get_bead_json(bead_id)
    if bead is None:
        click.echo(f"Error: bead '{bead_id}' not found", err=True)
        sys.exit(1)

    click.echo(json.dumps(build_handoff_packet(bead), indent=2))


@main.group()
def bridge() -> None:
    """Bridge Beads tasks to Hermes Kanban payloads."""


@bridge.command("dispatch")
@click.option("--dry-run", is_flag=True, help="Print planned Kanban payloads without side effects")
def bridge_dispatch(dry_run: bool) -> None:
    """Map ready beads to Hermes Kanban task payloads."""
    if not dry_run:
        click.echo("Error: live dispatch is not implemented; use --dry-run", err=True)
        sys.exit(1)
    tasks = [build_kanban_payload(bead) for bead in get_ready_beads()]
    click.echo(json.dumps({"tasks": tasks}, indent=2))


@bridge.command("sync-results")
@click.option("--dry-run", is_flag=True, help="Print planned bd operations without side effects")
@click.option("--results-file", type=click.Path(exists=True, dir_okay=False), required=True)
def bridge_sync_results(dry_run: bool, results_file: str) -> None:
    """Map Hermes Kanban results back to Beads operations."""
    if not dry_run:
        click.echo("Error: live result sync is not implemented; use --dry-run", err=True)
        sys.exit(1)
    results = json.loads(Path(results_file).read_text())
    if isinstance(results, dict):
        results = results.get("results", [])
    click.echo(json.dumps({"operations": build_result_sync_operations(list(results))}, indent=2))


@bridge.command("profile")
@click.argument("bead_id")
@click.option("--dry-run", is_flag=True, help="Print selected profile without side effects")
def bridge_profile(bead_id: str, dry_run: bool) -> None:
    """Select the Hermes profile for a bead using gate/metadata rules."""
    if not dry_run:
        click.echo("Error: live profile routing is not implemented; use --dry-run", err=True)
        sys.exit(1)
    bead = get_bead_json(bead_id)
    if bead is None:
        click.echo(f"Error: bead '{bead_id}' not found", err=True)
        sys.exit(1)
    click.echo(json.dumps({"bead_id": bead_id, "hermes_profile": select_profile(bead)}, indent=2))


if __name__ == "__main__":
    main()
