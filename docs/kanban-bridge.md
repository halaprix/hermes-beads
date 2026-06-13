# Hermes Kanban Dispatch Bridge

## Overview

The Hermes Kanban dispatch bridge is the integration layer between Beads (durable task graph) and Hermes Kanban (execution queue). It reads ready beads from Beads, creates Hermes Kanban tasks, and writes `kanban_task_id` back to the bead's metadata so results sync back to Beads.

## Architecture

- **Beads** is the source of truth for WHAT to do (durable, versioned, git-synced)
- **Hermes Kanban** is the execution queue for WHO does it (isolated worker processes)
- **The bridge** is the adapter between them

```
Beads (source of truth)          Hermes Kanban (execution queue)
┌─────────────────────┐         ┌─────────────────────────┐
│  bd ready --json    │──Bridge──│  hermes kanban create    │
│  bd show <id>       │         │  hermes kanban show      │
│  bd comments add <id>│         │  hermes kanban complete  │
│  bd close <id>       │         └─────────────────────────┘
└─────────────────────┘
```

### Data Flow

1. Bridge reads `bd ready --json` to get all unblocked, open beads
2. For each ready bead, bridge creates a Hermes Kanban task with the handoff packet as the task body
3. Bridge writes `metadata.hermes_kanban_task_id` back to the bead
4. Worker picks up the Kanban task, executes, writes result/failure to the task
5. Bridge syncs the result back to Beads as a comment and closes the bead

## Implementation Phases

### Phase 1 (this plan)
Bridge design and API surface. No live execution.

### Phase 2
Implemented as `hb bridge dispatch --dry-run`. It reads `bd ready --json`, builds handoff packets, and prints the Hermes Kanban payloads it would create. Live dispatch remains guarded until the controller enables it explicitly.

### Phase 3
Implemented as `hb bridge sync-results --dry-run --results-file <file>`. It maps completed/failed Hermes Kanban result records back into Beads comment/close/metadata operations. Live mutation remains guarded until the controller enables it explicitly.

### Phase 4
Documented in `docs/cron-polling.md`. The cron loop should run dispatch and result-sync on a conservative schedule and stay silent when nothing changed.

## API Surface

### Beads Commands
- `bd ready --json` — source of truth for available work
- `bd show <id> --json` — construct handoff packet for a bead
- `bd comments add <id> "result: ..."` — write execution result back to Beads
- `bd close <id> --reason "..."` — close bead after execution

### Hermes Kanban CLI
- `hermes kanban create` — create a new kanban task
- `hermes kanban show` — view task details
- `hermes kanban complete` — mark task complete with result

### Metadata Field
- `hermes_kanban_task_id` — written by bridge to track linkage between bead and kanban task

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Bead not found | Skip, log |
| Kanban task creation fails | Retry up to 3 times, then mark bead as failed |
| Worker timeout | Bridge marks bead as failed with iteration increment |
| Result sync fails | Keep kanban task open, retry on next bridge run |

## Result Sync — Idempotency

When `hb bridge sync-results` processes a result file, it applies operations (comments, close, metadata updates) to each bead. The bridge is designed to be **exactly-once per result record**: re-running the same result file against the same bead produces the same final state, without duplicate comments or repeated iteration increments.

### Operation IDs

Every non-skipped result record gets a deterministic **operation ID** that is embedded in the Beads comment as an idempotency token:

```
hermes-beads-op: <bead_id>-<sha256_prefix>
```

The op ID is the bead ID, a hyphen, and the first 8 hex characters of:

```
SHA-256(bead_id + "\n" + dispatch_id + "\n" + status + "\n" + summary)
```

The fields are joined with literal newline characters (`\n`, ASCII 0x0A), not the `||` separator — the `||` is shorthand in conversation, not the wire format. `status` is the normalized status (`completed` or `failed`) and `dispatch_id` is the Hermes Kanban task ID, defaulting to `"unknown"` if the result record omits it.

The same four inputs always produce the same op ID. The ID is not random: it is a stable hash, so it can be re-derived from the result record alone and matched against prior comments.

Example comment body:

```
hermes-beads-op: hb-xaz-8262b954
result: all tests passing
```

### Re-run Detection

On every invocation, `build_result_sync_operations` reads the existing comments for every bead referenced in the result file, scans each comment body for the `hermes-beads-op:` marker, and collects the op IDs already present. Before any mutation, the bridge compares the freshly-computed op ID for each result record against the set seen in comments:

- **First run (or new result record):** the op ID is unseen, so the bridge adds the op-marked comment, then either closes the bead (status `completed`) or updates `hermes_status: failed` and increments `hermes_iteration` (status `failed`).
- **Re-run with the same result file:** the op ID is already present in the existing comments, so the bridge emits a `skipped` operation with reason `"already applied"` for that record. **No mutation occurs.** The bead's state, comments, and iteration counter are unchanged.
- **Mixed re-run (partial overlap):** op IDs for new records are applied; op IDs for already-applied records are skipped. The two cases are independent.

This is what "exactly-once per result record" means: a given `(bead_id, dispatch_id, status, summary)` tuple mutates the bead at most one time, no matter how many times `sync-results` is run with the same input.

### Skipped Diagnostics

Malformed result records are emitted as `skipped` operations with a reason, so dry-run output is self-documenting without mutating anything. The skipped reasons are stable and parsable:

| Problem | Reason in skipped op |
|---------|---------------------|
| Missing `bead_id` / `source_bead_id` | `"missing bead_id in result record"` |
| Unrecognized `status` value | `"unknown status: '...'"` |
| Operation already applied (op ID exists in comments) | `"already applied"` |

The full set of `(op, bead_id, body|reason|metadata)` tuples is returned by `build_result_sync_operations` and printed by the CLI. The same operation list is what `apply_result_sync_operations` would execute, so dry-run and apply share the same emission logic and the same idempotency guarantees.

## Privacy and Security

- Handoff packets must not contain private IPs, tokens, or machine paths
- Only public-safe metadata fields are copied into Kanban task bodies
- The bridge runs in the Hermes controller environment, not on worker machines

## Future Considerations

- **Gate-based dispatch** — use Beads gate resolution to decide which profile handles a bead
- **Parallel worker coordination** — multiple workers picking from the same Beads queue
- **DoltHub sync** — cross-machine Beads state (currently uses local embedded Dolt)
