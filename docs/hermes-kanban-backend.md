# Hermes Kanban CLI Contract

**Decision: GO**, with one caveat.

The current `hermes kanban` CLI surface is stable enough for a backend to consume today, but consumers must **not** treat exit code alone as the failure signal for lookup-style commands. In the current build, some missing-task lookups print an error to stderr and still exit `0`.

This document freezes the command/JSON contract we observed against a clean temporary `HERMES_HOME`.

## Contract Scope

The backend contract covers:

- board bootstrap
- task creation and listing
- task lookup and lifecycle transitions
- worker claim output
- dispatch dry-run / dispatch planning output
- stats output
- the currently observed failure modes

Use a clean environment for validation:

```bash
export HERMES_HOME="$(mktemp -d)"
hermes kanban init
```

`hermes kanban init` is idempotent and produces no output on success.

## Boards

### `hermes kanban boards list --json`

Observed shape:

```json
[
  {
    "slug": "default",
    "name": "Default",
    "description": "",
    "icon": "",
    "color": "",
    "default_workdir": null,
    "created_at": null,
    "archived": false,
    "db_path": "/tmp/.../home/kanban.db",
    "is_current": true,
    "counts": {},
    "total": 0
  }
]
```

Notes:
- `default` always exists.
- `db_path` is board-local and should be treated as internal state, not API surface.
- `counts` is status-summary metadata.

### `hermes kanban boards create <slug> [--switch] [--default-workdir ...]`

This creates a new board record.
No JSON output was required for the backend contract in the current workflow; the main consumer is `boards list --json`.

## Task Creation and Lookup

### `hermes kanban create <title> ... --json`

Observed shape:

```json
{
  "id": "t_5b74ab1b",
  "title": "Spec freeze test",
  "body": "Verify CLI contract",
  "assignee": "docs",
  "status": "ready",
  "priority": 7,
  "tenant": null,
  "workspace_kind": "scratch",
  "workspace_path": null,
  "branch_name": null,
  "created_by": "user",
  "created_at": 1781354112,
  "started_at": null,
  "completed_at": null,
  "result": null,
  "skills": [],
  "max_retries": null,
  "session_id": null,
  "workflow_template_id": null,
  "current_step_key": null
}
```

Notes:
- `status` is `ready` by default.
- `assignee` is preserved as plain text.
- `workspace_kind` defaults to `scratch`.

### `hermes kanban list --json`

Returns an array of task objects with the same shape as `create --json`.

### `hermes kanban show <task_id> --json`

Observed shape:

```json
{
  "task": { ...same task fields as create/list... },
  "latest_summary": null,
  "parents": [],
  "children": [],
  "comments": [],
  "events": [
    {
      "kind": "created",
      "payload": {
        "assignee": "docs",
        "status": "ready",
        "parents": [],
        "tenant": null,
        "branch_name": null,
        "skills": null,
        "goal_mode": null
      },
      "created_at": 1781354112,
      "run_id": null
    }
  ],
  "runs": []
}
```

Notes:
- `show` is the richest lookup shape.
- The backend can use `task.status`, `comments`, `events`, and `runs` to reconcile lifecycle.

## Worker Claim and Lifecycle Commands

### `hermes kanban claim <task_id>`

Success output:

```text
Claimed t_5b74ab1b
Workspace: /tmp/.../home/kanban/workspaces/t_5b74ab1b
```

Contract notes:
- The workspace path is the important machine-readable part.
- On success, the task transitions to a running/claimed state.

### `hermes kanban comment <task_id> <text...>`

Success output:

```text
Comment added to t_5b74ab1b
```

### `hermes kanban complete <task_ids...> --result ... --summary ... --metadata ...`

Success output:

```text
Completed t_609716e7
```

Observed state transition after completion:
- `task.status` becomes `done`
- `task.result` is set from `--result`
- `task.completed_at` is populated
- `show --json` includes a run record with `outcome: "completed"`
- `latest_summary` is taken from `--summary`

### `hermes kanban block <task_id> [reason ...]`

Success output:

```text
Blocked t_1bc5573c: needs review
```

Observed state transition:
- task status becomes blocked
- a blocking comment is added
- the latest run is marked blocked

### `hermes kanban unblock <task_id> [--reason ...]`

Success output:

```text
Unblocked t_1bc5573c: cleared
```

Observed state transition:
- task returns to `ready`
- an unblock comment is added
- the previous block comment remains in history

## Dispatch Contract

### `hermes kanban dispatch --dry-run --json`

Observed output shape:

```json
{
  "reclaimed": 0,
  "crashed": [],
  "timed_out": [],
  "stale": [],
  "auto_blocked": [],
  "promoted": 0,
  "spawned": [],
  "skipped_unassigned": [],
  "skipped_nonspawnable": ["t_54c644a8"],
  "skipped_per_profile_capped": [],
  "auto_assigned_default": []
}
```

Important notes:
- The dispatch command is a **planner / dispatcher pass**, not a board-rewrite command.
- For tasks assigned to profiles that are not spawnable in the current environment, the task ID appears under `skipped_nonspawnable`.
- When nothing is spawnable, `spawned` stays empty and the command still succeeds.

The backend must treat this output as the contract, not the mere presence of a task in `ready` state.

## Stats Contract

### `hermes kanban stats --json`

Observed shape:

```json
{
  "by_status": {
    "ready": 1
  },
  "by_assignee": {
    "docs": {
      "ready": 1
    }
  },
  "oldest_ready_age_seconds": 1,
  "now": 1781354121
}
```

This is useful for dashboarding and sanity checks, but it is not the authoritative state store.

## Failure Modes We Observed

### 1) Missing-task lookups print an error but still exit `0`

These commands both printed `no such task: no-such-task` to stderr and exited with code `0` in the current build:

```bash
hermes kanban show no-such-task --json
hermes kanban claim no-such-task
```

This is the main caveat for consumers:
- do **not** rely on exit code alone for lookup commands
- treat stderr text / absent stdout payload as the failure signal for missing IDs

### 2) Dispatch can legitimately skip work

If the assignee/profile is not spawnable in the current environment, dispatch returns success and records the task under `skipped_nonspawnable`.

### 3) Board bootstrap is idempotent

`hermes kanban init` can be run repeatedly and does not mutate useful state after the first initialization.

## Stop / Go Decision

**Go.**

The CLI contract is usable as-is for the current Hermes-beads backend work, provided consumers follow these rules:

- parse JSON outputs for `create`, `list`, `show`, `stats`, and `dispatch --json`
- treat `show`/`claim` missing-task stderr text as the failure signal
- treat `dispatch` as advisory/planning output when the environment cannot spawn the assignee profile
- preserve the board-local DB and task lifecycle as the source of truth

That is the contract frozen by this bead.
