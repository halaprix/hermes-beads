# Hermes Backend Operations

The `hermes-cli` backend is the production bridge between Beads and Hermes Kanban.
It is intentionally implemented outside Hermes core: Beads remains the durable task graph, Hermes remains the worker runtime, and `hb` is the adapter.

## Command boundary

```bash
hb bridge dispatch --dry-run
hb bridge dispatch --apply --backend hermes-cli
```

The dry-run command prints the Beads-derived task payloads. Apply replays the same plan through `hermes kanban create`, then writes the returned task ID back to the bead as `metadata.hermes_kanban_task_id` and gates the bead to `in_progress`.

## Required Hermes CLI surface

The backend consumes only stable CLI commands:

- `hermes kanban create <title> --json`
- `hermes kanban show <task-id> --json`
- `hermes kanban complete <task-id> ...` for future result flows

It does not import Hermes internals and does not require a Hermes core patch.

## Idempotency and failure semantics

Each dispatched payload includes `idempotency_key: <bead_id>`, forwarded as:

```bash
hermes kanban create ... --idempotency-key <bead-id>
```

This protects the window where Hermes task creation succeeds but Beads metadata linkage fails before retry. After a task is created, task lookup via `show` is best-effort output enrichment. If lookup fails after Beads linkage has already been written, `hb` returns a minimal task record containing the task ID instead of turning a successful mutation into a retryable failure.

Failure rules:

- create failure: Beads remains unchanged
- link/status failure after create: retry is safe because the create call is idempotent by bead ID
- show failure after link/status: command succeeds with minimal output
- repeated dispatch after successful link: bead is skipped because `metadata.hermes_kanban_task_id` exists and status is no longer ready

## Operational limitations

- `hb` shells out to `bd` and `hermes`; both must be on `PATH`.
- The bridge supports Beads workspaces where `bd` auto-discovers the workspace from the current directory.
- `hermes_status` is advisory. The Beads `status` field and `metadata.hermes_kanban_task_id` are the dispatch gate.
- The bridge is not a worker scheduler, process supervisor, or control plane.

## Skill boundary

The Hermes skill should teach users how to run `bd`, `hb`, and Hermes Kanban together. It should not add a Hermes core tool that mutates Beads directly. Keeping the adapter as a package keeps failure handling testable and keeps Beads project state portable outside Hermes.
