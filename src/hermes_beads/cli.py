"""CLI for hermes-beads.

All bridge commands are dry-run-first. Commands that would mutate Hermes or
Beads state require explicit non-dry-run support before they can run live.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import click

from hermes_beads.bd_helpers import check_bd_available, run_bd, run_bd_json
from hermes_beads.dispatch_ops import (
    DispatchOpKind,
    build_dispatch_plan,
)
from hermes_beads.local_file_backend import LocalFileQueueBackend
from hermes_beads.hermes_kanban_backend import (
    HermesKanbanBackend,
    HermesKanbanBackendError,
)
from hermes_beads.result_ops import OpStatus, build_op_id, parse_op_marker
from hermes_beads.tick_ops import TickLock, TickLockError, build_tick_plan, load_results_file, tick_summary
from hermes_beads.dashboard import collect_dashboard_data, write_dashboard
from hermes_beads.gates import bead_requires_review, build_gate_approval_plan, escalation_metadata, gate_for_bead, list_gates

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def get_version() -> str:
    """Return the installed package version, with a source-tree fallback."""
    version_file = REPO_ROOT / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    try:
        return version("hermes-beads")
    except PackageNotFoundError:
        return "0+unknown"


def _json_env(name: str) -> Any | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    return json.loads(raw)


def get_bead_json(bead_id: str) -> dict[str, Any] | None:
    """Get bead data via bd show --json."""
    mock_data = _json_env("HB_MOCK_BD_SHOW_JSON")
    if mock_data is not None:
        beads = mock_data
    else:
        beads = run_bd_json(["show", bead_id, "--json"])

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
    data = run_bd_json(["ready", "--json"])
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
        # If mock data has bead_id fields, filter to the requested bead.
        # If no bead_id field (backward compat), return as-is.
        if mock_data and isinstance(mock_data[0], dict) and "bead_id" in mock_data[0]:
            mock_data = [c for c in mock_data if c.get("bead_id") == bead_id]
        return normalize_comments(mock_data)

    # If any BD mock is set but HB_MOCK_BD_COMMENTS_JSON is not, we're in a
    # test environment — skip the real bd call and return empty.
    if _json_env("HB_MOCK_BD_SHOW_JSON") is not None or _json_env("HB_MOCK_BD_READY_JSON") is not None:
        return []

    # Some bd show JSON versions may embed comments directly.
    embedded = normalize_comments((bead or {}).get("comments"))
    if embedded:
        return embedded

    return normalize_comments(run_bd_json(["comments", bead_id, "--json"]))


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
    profile, _reason = explain_profile_selection(bead)
    return {
        "bead_id": bead_id,
        "goal": bead.get("title", ""),
        "description": bead.get("description", ""),
        "stop_condition": metadata.get("hermes_stop_condition", ""),
        "hermes_profile": profile,
        "hermes_mode": metadata.get("hermes_mode", ""),
        "dependencies": _dependency_summary(bead),
        "comments": get_comments(bead_id, bead),
        "iteration": int(metadata.get("hermes_iteration", 0) or 0),
    }


def select_profile(bead: dict[str, Any]) -> str:
    """Choose the Hermes profile for a bead without embedding policy in Beads."""
    profile, _reason = explain_profile_selection(bead)
    return profile


def explain_profile_selection(bead: dict[str, Any]) -> tuple[str, str]:
    """Choose a Hermes profile and explain the selected routing rule."""
    metadata = bead.get("metadata", {}) or {}
    explicit = metadata.get("hermes_profile")
    if explicit:
        return str(explicit), "explicit metadata.hermes_profile"

    labels = set(bead.get("labels", []) or [])
    if bead_requires_review(bead):
        return "reviewer", "review gate requested"
    if "docs" in labels:
        return "docs", "labels include docs"
    if "planning" in labels or "architecture" in labels:
        return "planner", "labels include planning or architecture"
    return "ts-dev", "default profile"


def build_kanban_payload(bead: dict[str, Any]) -> dict[str, Any]:
    """Map a ready bead to a Hermes Kanban task payload.

    This wrapper preserves the existing CLI dry-run wire format by
    building the full handoff packet, including comments gathered from
    Beads. The pure planner in :mod:`hermes_beads.dispatch_ops` can use
    an IO-free payload builder for unit tests, while the Click adapter
    injects this richer builder for CLI output compatibility.
    """
    packet = build_handoff_packet(bead)
    bead_id = packet["bead_id"]
    profile = select_profile(bead)
    return {
        "source": "beads",
        "source_bead_id": bead_id,
        "idempotency_key": bead_id,
        "title": f"{bead_id}: {packet['goal']}",
        "assignee": profile,
        "priority": bead.get("priority", 2),
        "mode": (bead.get("metadata", {}) or {}).get("hermes_mode", "pr"),
        "body": json.dumps(packet, indent=2),
    }


def dispatch_linked_task_id(bead: dict[str, Any]) -> str:
    """Return the existing dispatch link ID, if any."""
    metadata = bead.get("metadata", {}) or {}
    task_id = metadata.get("hermes_kanban_task_id")
    return str(task_id or "")


def dispatch_bead_is_linked(bead: dict[str, Any]) -> bool:
    """Return whether a bead already has a dispatch/task link."""
    return bool(dispatch_linked_task_id(bead))


def dispatch_candidates(ready_beads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter ready beads down to ones without a dispatch link."""
    return [bead for bead in ready_beads if not dispatch_bead_is_linked(bead)]


def write_dispatch_link(bead_id: str, task_id: str) -> None:
    """Write the dispatched task id back to Beads metadata."""
    run_bd(["update", bead_id, "--set-metadata", f"hermes_kanban_task_id={task_id}"])


def gate_dispatch_bead(bead_id: str) -> None:
    """Mark a dispatched bead in_progress so it leaves the ready queue."""
    run_bd(["update", bead_id, "--status", "in_progress"])


def next_iteration(bead: dict[str, Any]) -> int:
    """Return the next retry iteration for a failed/timeout bead."""
    metadata = bead.get("metadata", {}) or {}
    return int(metadata.get("hermes_iteration", 0) or 0) + 1


def build_result_sync_operations(
    results: list[dict[str, Any]],
    existing_comments: dict[str, list[dict[str, str]]] | None = None,
) -> list[dict[str, Any]]:
    """Map Hermes Kanban result records into dry-run bd operations.

    Parameters
    ----------
    results:
        List of result dicts from Hermes Kanban (each must contain bead_id
        and status; may contain dispatch_id and summary).
    existing_comments:
        Optional mapping of bead_id -> list of comment dicts. Each comment
        dict must have a ``body`` field. If provided, any result whose
        operation ID is already present in an existing comment's
        ``hermes-beads-op:`` marker is emitted as a ``skipped`` operation
        instead of a real write.
    """
    existing_comments = existing_comments or {}
    operations: list[dict[str, Any]] = []
    for result in results:
        bead_id = result.get("bead_id") or result.get("source_bead_id")
        if not bead_id:
            operations.append({"op": "skipped", "bead_id": "", "reason": "missing bead_id in result record"})
            continue
        dispatch_id = result.get("dispatch_id", "unknown")
        status = result.get("status", "")
        summary = result.get("summary", "")

        op_status = OpStatus.COMPLETED if status in {"completed", "success", "done"} else OpStatus.FAILED
        op_id = build_op_id(bead_id, dispatch_id, op_status, summary)
        seen_ids: set[str] = set()
        for comment in existing_comments.get(bead_id, []):
            marker = parse_op_marker(comment.get("body", ""))
            if marker:
                seen_ids.add(marker)

        if op_id in seen_ids:
            operations.append({"op": "skipped", "bead_id": bead_id, "reason": "already applied"})
            continue

        if status in {"completed", "success", "done"}:
            comment_body = f"hermes-beads-op: {op_id}\nresult: {summary}"
            operations.append({"op": "comment", "bead_id": bead_id, "body": comment_body})
            operations.append({"op": "close", "bead_id": bead_id, "reason": "kanban task completed"})
        elif status in {"failed", "timeout", "error"}:
            bead = get_bead_json(str(bead_id)) or {"id": bead_id, "metadata": {}}
            iteration = next_iteration(bead)
            metadata = {"hermes_status": "failed", "hermes_iteration": iteration}
            threshold = int((bead.get("metadata", {}) or {}).get("hermes_retry_escalation_threshold", 3) or 3)
            metadata.update(escalation_metadata(iteration, threshold))
            comment_body = f"hermes-beads-op: {op_id}\nfailed: {summary}"
            operations.append({"op": "comment", "bead_id": bead_id, "body": comment_body})
            operations.append(
                {
                    "op": "update-metadata",
                    "bead_id": bead_id,
                    "metadata": metadata,
                }
            )
        else:
            operations.append({"op": "skipped", "bead_id": bead_id, "reason": f"unknown status: {status!r}"})
    return operations


def apply_result_sync_operations(operations: list[dict[str, Any]]) -> None:
    """Apply result-sync operations to the local Beads workspace."""
    for operation in operations:
        bead_id = str(operation["bead_id"])
        if operation["op"] == "comment":
            run_bd(["comments", "add", bead_id, str(operation["body"])])
        elif operation["op"] == "close":
            run_bd(["close", bead_id, "--reason", str(operation["reason"])])
        elif operation["op"] == "update-metadata":
            args = ["update", bead_id]
            for key, value in operation.get("metadata", {}).items():
                args.extend(["--set-metadata", f"{key}={value}"])
            run_bd(args)


def _run_command(args: list[str]) -> None:
    """Run an external command, raising a Click exception on failure."""
    try:
        subprocess.run(args, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise click.ClickException(f"command not found: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        msg = f"{' '.join(args)} failed"
        if stderr:
            msg += f": {stderr}"
        raise click.ClickException(msg) from exc


def _dispatch_apply(backend: str, queue_file: Path | None, plan: list[Any]) -> list[dict[str, Any]]:
    """Apply a dispatch plan through the selected backend."""
    if backend == "local-file":
        if queue_file is None:
            raise click.ClickException("--queue-file is required for --backend local-file")
        dispatch_backend: Any = LocalFileQueueBackend(queue_file, project_root=Path.cwd())
    elif backend == "hermes-cli":
        dispatch_backend = HermesKanbanBackend()
    else:
        raise click.ClickException(f"unsupported dispatch backend: {backend}")
    applied_tasks: list[dict[str, Any]] = []
    for op in plan:
        if op.kind is not DispatchOpKind.CREATE:
            continue
        bead_id = str(op.payload.get("source_bead_id", ""))
        task_id = dispatch_backend.create(op.payload)
        if bead_id:
            write_dispatch_link(bead_id, task_id)
            gate_dispatch_bead(bead_id)
        try:
            task = dispatch_backend.show(task_id)
        except HermesKanbanBackendError:
            task = {"id": task_id}
        if task is not None:
            applied_tasks.append(task)
    return applied_tasks


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

    if _json_env("HB_MOCK_BD_READY_JSON") is None:
        check_bd_available()

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

    if _json_env("HB_MOCK_BD_SHOW_JSON") is None and _json_env("HB_MOCK_BD_COMMENTS_JSON") is None:
        check_bd_available()

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
@click.option("--apply", "apply_ops", is_flag=True, help="Apply planned tasks through a dispatch backend")
@click.option("--backend", type=click.Choice(["local-file", "hermes-cli"]), default=None, help="Dispatch backend to use when applying")
@click.option("--queue-file", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Queue file for the local-file backend")
def bridge_dispatch(dry_run: bool, apply_ops: bool, backend: str | None, queue_file: Path | None) -> None:
    """Map ready beads to Hermes Kanban task payloads.

    Planning logic lives in :mod:`hermes_beads.dispatch_ops`; this
    command is a thin Click/IO adapter that delegates to the pure
    planner. Dry-run stays JSON-only. Apply is supported through the
    selected backend, which may either write deterministic queue records
    to a JSON file or shell out to the Hermes CLI.
    """
    if dry_run == apply_ops:
        click.echo("Error: choose exactly one of --dry-run or --apply", err=True)
        sys.exit(1)
    if _json_env("HB_MOCK_BD_READY_JSON") is None:
        check_bd_available()
    ready_beads = get_ready_beads()
    dispatch_beads = dispatch_candidates(ready_beads)
    plan = build_dispatch_plan(dispatch_beads, payload_builder=build_kanban_payload)
    if dry_run:
        tasks = [op.payload for op in plan if op.kind is DispatchOpKind.CREATE]
        click.echo(json.dumps({"tasks": tasks}, indent=2))
        return
    if backend is None:
        click.echo("Error: choose a dispatch backend with --backend", err=True)
        sys.exit(1)
    if backend == "local-file":
        if queue_file is None:
            click.echo("Error: --queue-file is required for --backend local-file", err=True)
            sys.exit(1)
        dispatch_backend: Any = LocalFileQueueBackend(queue_file, project_root=Path.cwd())
    elif backend == "hermes-cli":
        dispatch_backend = HermesKanbanBackend()
    else:
        click.echo(f"Error: unsupported dispatch backend: {backend}", err=True)
        sys.exit(1)
    applied_tasks: list[dict[str, Any]] = []
    try:
        for op in plan:
            if op.kind is not DispatchOpKind.CREATE:
                continue
            bead_id = str(op.payload.get("source_bead_id", ""))
            task_id = dispatch_backend.create(op.payload)
            if bead_id:
                write_dispatch_link(bead_id, task_id)
                gate_dispatch_bead(bead_id)
            try:
                task = dispatch_backend.show(task_id)
            except HermesKanbanBackendError:
                # The task was already created and linked in Beads. Treat
                # lookup as best-effort output enrichment so a transient
                # post-create `show` failure does not turn a successful
                # mutation into a retryable CLI failure.
                task = {"id": task_id}
            if task is not None:
                applied_tasks.append(task)
    except HermesKanbanBackendError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    output: dict[str, Any] = {
        "backend": backend,
        "applied": True,
        "tasks": applied_tasks,
    }
    if backend == "local-file":
        output["queue_file"] = str(dispatch_backend.queue_file)
    click.echo(json.dumps(output, indent=2))


@bridge.command("tick")
@click.option("--dry-run", is_flag=True, help="Print tick plan without side effects")
@click.option("--apply", "apply_ops", is_flag=True, help="Run one bridge tick")
@click.option("--backend", type=click.Choice(["local-file", "hermes-cli"]), default="local-file")
@click.option("--queue-file", type=click.Path(dir_okay=False, path_type=Path), default=Path(".hermes-beads/dispatch.json"))
@click.option("--results-file", type=click.Path(exists=True, dir_okay=False, path_type=Path), default=None)
@click.option("--lock-file", type=click.Path(dir_okay=False, path_type=Path), default=Path(".hermes-beads/tick.lock"))
@click.option("--stale-after", type=int, default=3600, help="Seconds after which a tick lock is stale")
@click.option("--privacy-scan", is_flag=True, help="Run scripts/scan-privacy.sh before mutating")
@click.option("--git-pull", is_flag=True, help="Run git pull --rebase before mutating")
@click.option("--git-push", is_flag=True, help="Run git push after successful mutation")
@click.option("--bd-pull", is_flag=True, help="Run bd dolt pull before mutating")
@click.option("--bd-push", is_flag=True, help="Run bd dolt push after successful mutation")
@click.option("--silent-noop", is_flag=True, help="Emit no stdout when a tick has no work")
def bridge_tick(
    dry_run: bool,
    apply_ops: bool,
    backend: str,
    queue_file: Path,
    results_file: Path | None,
    lock_file: Path,
    stale_after: int,
    privacy_scan: bool,
    git_pull: bool,
    git_push: bool,
    bd_pull: bool,
    bd_push: bool,
    silent_noop: bool,
) -> None:
    """Plan or run one cron-friendly bridge tick."""
    if dry_run == apply_ops:
        click.echo("Error: choose exactly one of --dry-run or --apply", err=True)
        sys.exit(1)
    check_bd_available()
    if dry_run:
        ready_beads = get_ready_beads()
        dispatch_beads = [bead for bead in dispatch_candidates(ready_beads) if not gate_for_bead(bead)]
        results = load_results_file(results_file)
        tick_plan = build_tick_plan(dispatch_beads, results, backend=backend, queue_file=str(queue_file))
        if silent_noop and tick_plan.is_noop:
            return
        click.echo(json.dumps(tick_plan.to_dict(), indent=2))
        return
    try:
        with TickLock(lock_file, stale_after_seconds=stale_after):
            if privacy_scan:
                _run_command(["bash", "scripts/scan-privacy.sh"])
            if git_pull:
                _run_command(["git", "pull", "--rebase"])
            if bd_pull:
                run_bd(["dolt", "pull"])
            ready_beads = get_ready_beads()
            dispatch_beads = [bead for bead in dispatch_candidates(ready_beads) if not gate_for_bead(bead)]
            results = load_results_file(results_file)
            plan = build_dispatch_plan(dispatch_beads, payload_builder=build_kanban_payload)
            tick_plan = build_tick_plan(dispatch_beads, results, backend=backend, queue_file=str(queue_file))
            applied_tasks = _dispatch_apply(backend, queue_file, plan) if tick_plan.dispatch_count else []
            result_operations: list[dict[str, Any]] = []
            if results is not None:
                result_list = results.get("results", []) if isinstance(results, dict) else results
                existing_comments: dict[str, list[dict[str, str]]] = {}
                for result in result_list:
                    bead_id = str(result.get("bead_id") or result.get("source_bead_id") or "")
                    if bead_id and bead_id not in existing_comments:
                        comments = get_comments(bead_id)
                        existing_comments[bead_id] = [{"body": c.get("body", "")} for c in comments]
                result_operations = build_result_sync_operations(list(result_list), existing_comments)
                apply_result_sync_operations(result_operations)
            if bd_push:
                run_bd(["dolt", "push"])
            if git_push:
                _run_command(["git", "push"])
    except (TickLockError, HermesKanbanBackendError, click.ClickException) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    if silent_noop and tick_plan.is_noop:
        return
    click.echo(
        json.dumps(
            {
                "applied": True,
                "summary": tick_summary(tick_plan, applied=True),
                "tasks": applied_tasks,
                "result_operations": result_operations,
            },
            indent=2,
        )
    )


@bridge.command("sync-results")
@click.option("--dry-run", is_flag=True, help="Print planned bd operations without side effects")
@click.option("--apply", "apply_ops", is_flag=True, help="Apply bd operations to the current Beads workspace")
@click.option("--results-file", type=click.Path(exists=True, dir_okay=False), required=True)
def bridge_sync_results(dry_run: bool, apply_ops: bool, results_file: str) -> None:
    """Map Hermes Kanban results back to Beads operations."""
    if dry_run == apply_ops:
        click.echo("Error: choose exactly one of --dry-run or --apply", err=True)
        sys.exit(1)
    if _json_env("HB_MOCK_BD_SHOW_JSON") is None:
        check_bd_available()
    results = json.loads(Path(results_file).read_text())
    if isinstance(results, dict):
        results = results.get("results", [])
    # Build existing_comments map: bead_id -> list of comment dicts (with 'body' field)
    existing_comments: dict[str, list[dict[str, str]]] = {}
    for result in results:
        bead_id = str(result.get("bead_id") or result.get("source_bead_id") or "")
        if bead_id and bead_id not in existing_comments:
            comments = get_comments(bead_id)
            existing_comments[bead_id] = [{"body": c.get("body", "")} for c in comments]
    operations = build_result_sync_operations(list(results), existing_comments)
    if apply_ops:
        apply_result_sync_operations(operations)
    click.echo(json.dumps({"operations": operations, "applied": apply_ops}, indent=2))


@bridge.command("profile")
@click.argument("bead_id")
@click.option("--dry-run", is_flag=True, help="Print selected profile without side effects")
def bridge_profile(bead_id: str, dry_run: bool) -> None:
    """Select the Hermes profile for a bead using gate/metadata rules."""
    if not dry_run:
        click.echo("Error: live profile routing is not implemented; use --dry-run", err=True)
        sys.exit(1)
    if _json_env("HB_MOCK_BD_SHOW_JSON") is None:
        check_bd_available()
    bead = get_bead_json(bead_id)
    if bead is None:
        click.echo(f"Error: bead '{bead_id}' not found", err=True)
        sys.exit(1)
    profile, reason = explain_profile_selection(bead)
    click.echo(json.dumps({"bead_id": bead_id, "hermes_profile": profile, "reason": reason}, indent=2))


@main.group("gates")
def gates_group() -> None:
    """Inspect and plan approval-gate operations."""


@gates_group.command("list")
@click.option("--dry-run", is_flag=True, help="List gates without mutating")
def gates_list(dry_run: bool) -> None:
    """List pending approval gates from open Beads issues."""
    if not dry_run:
        click.echo("Error: gates list is dry-run only", err=True)
        sys.exit(1)
    beads = _json_env("HB_MOCK_BD_READY_JSON")
    if beads is None:
        check_bd_available()
        beads = run_bd_json(["list", "--status=open", "--json"])
    click.echo(json.dumps({"gates": list_gates(list(beads or [])), "applied": False}, indent=2))


@gates_group.command("approve")
@click.argument("bead_id")
@click.option("--dry-run", is_flag=True, help="Print approval plan without mutating")
def gates_approve(bead_id: str, dry_run: bool) -> None:
    """Plan approval of a single gate."""
    if not dry_run:
        click.echo("Error: gate approval apply is not implemented; use --dry-run", err=True)
        sys.exit(1)
    if _json_env("HB_MOCK_BD_SHOW_JSON") is None:
        check_bd_available()
    bead = get_bead_json(bead_id)
    if bead is None:
        click.echo(f"Error: bead '{bead_id}' not found", err=True)
        sys.exit(1)
    click.echo(json.dumps({"operation": build_gate_approval_plan(bead), "applied": False}, indent=2))


@main.group("dashboard")
def dashboard_group() -> None:
    """Build read-only static dashboard artifacts."""


@dashboard_group.command("build")
@click.option("--output", type=click.Path(dir_okay=False, path_type=Path), required=True)
@click.option("--dry-run", is_flag=True, help="Print collected data instead of writing HTML")
def dashboard_build(output: Path, dry_run: bool) -> None:
    """Build a static dashboard from Beads issue data."""
    beads = _json_env("HB_MOCK_BD_READY_JSON")
    if beads is None:
        check_bd_available()
        beads = run_bd_json(["list", "--json"])
    data = collect_dashboard_data(list(beads or []))
    if dry_run:
        rendered = json.dumps(data, indent=2)
        try:
            from hermes_beads.dashboard import assert_public_safe_dashboard

            assert_public_safe_dashboard(rendered)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(rendered)
        return
    try:
        path = write_dashboard(output, data)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps({"output": str(path), "items": len(data["items"]), "applied": True}, indent=2))


if __name__ == "__main__":
    main()
