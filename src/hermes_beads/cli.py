"""Minimal dry-run CLI for hermes-beads.

No live Hermes dispatch — dry-run only.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import click


def get_version() -> str:
    """Read version from VERSION file at repo root."""
    # cli.py is at src/hermes_beads/cli.py
    # go up two levels to repo root
    version_file = Path(__file__).resolve().parent.parent.parent / "VERSION"
    return version_file.read_text().strip()


def get_bead_json(bead_id: str) -> dict | None:
    """Get bead data via bd show --json."""
    try:
        result = subprocess.run(
            ["bd", "show", bead_id, "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        beads = json.loads(result.stdout)
        # bd show --json returns a list
        for bead in beads:
            if bead.get("id") == bead_id:
                return bead
        return None
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def get_ready_beads() -> list[dict]:
    """Get ready beads via bd ready --json."""
    try:
        result = subprocess.run(
            ["bd", "ready", "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return []


def build_handoff_packet(bead: dict) -> dict:
    """Build a handoff packet from bead data."""
    metadata = bead.get("metadata", {})
    dependencies = []
    for dep in bead.get("dependencies", []):
        dependencies.append({
            "id": dep.get("id", ""),
            "title": dep.get("title", ""),
            "status": dep.get("status", ""),
        })

    comments = []
    # Comments would come from bd comment list --json but for dry-run
    # we construct from available bead data

    return {
        "bead_id": bead.get("id", ""),
        "goal": bead.get("title", ""),
        "description": bead.get("description", ""),
        "stop_condition": metadata.get("hermes_stop_condition", ""),
        "hermes_profile": metadata.get("hermes_profile", ""),
        "hermes_mode": metadata.get("hermes_mode", ""),
        "dependencies": dependencies,
        "comments": comments,
        "iteration": metadata.get("hermes_iteration", 0),
    }


@click.group()
@click.version_option(version=get_version())
def main() -> None:
    """hermes-beads CLI — dry-run only, no live Hermes dispatch."""
    pass


@main.command()
@click.option("--dry-run", is_flag=True, help="Dry-run mode (no side effects)")
def ready(dry_run: bool) -> None:
    """Print handoff packet for the next ready bead."""
    if not dry_run:
        click.echo("Error: only --dry-run mode is supported", err=True)
        sys.exit(1)

    # Check for mock data in environment (for testing)
    mock_data = os.environ.get("HB_MOCK_BD_READY_JSON")
    if mock_data is not None:
        ready_beads = json.loads(mock_data)
    else:
        ready_beads = get_ready_beads()

    if not ready_beads:
        click.echo("Error: no ready beads found", err=True)
        sys.exit(1)

    bead = ready_beads[0]
    packet = build_handoff_packet(bead)
    click.echo(json.dumps(packet, indent=2))
    sys.exit(0)


@main.command()
@click.argument("bead_id")
@click.option("--dry-run", is_flag=True, help="Dry-run mode (no side effects)")
def handoff(bead_id: str, dry_run: bool) -> None:
    """Print handoff packet for the specified bead."""
    if not dry_run:
        click.echo("Error: only --dry-run mode is supported", err=True)
        sys.exit(1)

    # Check for mock data in environment (for testing)
    mock_data = os.environ.get("HB_MOCK_BD_SHOW_JSON")
    if mock_data is not None:
        beads = json.loads(mock_data)
        bead = None
        for b in beads:
            if b.get("id") == bead_id:
                bead = b
                break
    else:
        bead = get_bead_json(bead_id)

    if bead is None:
        click.echo(f"Error: bead '{bead_id}' not found", err=True)
        sys.exit(1)

    packet = build_handoff_packet(bead)
    click.echo(json.dumps(packet, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
