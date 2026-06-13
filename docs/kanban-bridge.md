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

#### Dispatch Planner and Backend Protocol

Dispatch planning is split from the Click command in `src/hermes_beads/dispatch_ops.py`:

- `DispatchOp` is the immutable operation record emitted by the planner. Current operation kinds are `create` and `skipped`.
- `build_dispatch_plan(ready_beads, backend=None, payload_builder=None)` maps ready bead dictionaries into `DispatchOp` records without calling Click, `bd`, network APIs, or backend mutation methods.
- `DispatchBackend` defines the future backend contract. The minimum dispatch-apply surface is `create(payload) -> task_id`; `show(task_id)` and `complete(task_id, status, summary)` are reserved for backends that also serve result-sync flows.
- `kanban_payload_for_bead(bead)` is the IO-free default payload builder used by unit tests. The CLI injects its existing richer `build_kanban_payload` wrapper so `bridge dispatch --dry-run` still emits full handoff bodies, including comments gathered from Beads.

This preserves the no-live-mutation contract for this phase: the planner describes what dispatch would do, and the CLI prints the planned create payloads. `hb bridge dispatch --apply --backend local-file --queue-file <path>` replays the same plan into the deterministic queue, writes `metadata.hermes_kanban_task_id` back to Beads, and gates the bead to `in_progress` so it leaves the ready queue. `hb bridge dispatch --apply --backend hermes-cli` uses the real Hermes Kanban CLI, then writes the returned task id back to Beads and gates the bead the same way. The Beads `status` field remains canonical; `hermes_status` is advisory only. Ready beads that already carry a dispatch link are skipped on subsequent runs.

### Phase 3


### Phase 4
Documented in `docs/cron-polling.md`. The cron loop should run dispatch and result-sync on a conservative schedule and stay silent when nothing changed.

The first local-file backend piece is implemented in `src/hermes_beads/local_file_backend.py`.
It now powers `hb bridge dispatch --apply --backend local-file --queue-file <path>`.
The backend creates deterministic queue records with stable `local-<sha256-prefix>` task IDs,
skips duplicate payloads by returning the existing ID without appending, raises a
clear error for corrupt queue JSON, and resolves relative queue-file paths against
the caller's project root.

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
