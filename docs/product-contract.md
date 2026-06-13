# Bridge Product Contract

> Authority model, mutation semantics, and idempotency rules for hermes-beads.
> Last updated: 2026-06-12.

## 1. Authority Model

### Beads Is Authoritative

Beads (the Dolt-backed task graph accessed via the `bd` CLI) is the **single source of truth**
for project task state. All authoritative data lives in a Beads workspace:

- Task graph (open/closed states, dependencies, priorities)
- Public metadata fields (`hermes_*`)
- Handoff comments (decisions, blockers, handoff notes)
- Execution routing hints (`hermes_profile`, `hermes_mode`)

No other system or file holds authoritative task state. Specifically:

| System | Role | Can create authoritative state? |
|--------|------|--------------------------------|
| Beads (bd CLI + Dolt DB) | Source of truth | Yes — durable, versioned, git-synced |
| Hermes Kanban | Execution queue | No — derived view; kanban tasks reference beads |
| Local-file queue (handoff packets) | Disposable staging | No — deletable after dispatch |
| Dashboard | Observability | No — read-only, never writes back |
| `.beads/issues.jsonl` | Passive export | No — stale by construction |

### Queues and Dashboards Are Derived/Disposable

**Hermes Kanban tasks** are execution work items created by the bridge from ready beads. They are
disposable: if the Kanban board is wiped, the bridge can re-create them by reading Beads. A
kanban task's identity is tracked in bead metadata (`hermes_kanban_task_id`) only for result
matching — losing it is recoverable.

**Local-file dispatch queue** (handoff packet files on disk) is a staging area for testing the
bridge contract without a live Hermes instance. These files are deletable; the bridge re-reads
Beads to reconstruct them.

**Dashboards** are observability surfaces derived from `bd` commands. They never write to Beads
or any other authoritative store. See [`docs/dashboard.md`](dashboard.md).

## 2. Current Live Mutation Path

The only live mutation path as of v1.0.1 is **`hb bridge sync-results --apply`**.

### `hb bridge sync-results`

```
hb bridge sync-results --results-file <file> --dry-run      # preview only
hb bridge sync-results --results-file <file> --apply         # mutates Beads
```

**Input:** a JSON results file (Hermes Kanban completion records or test fixtures).

**Output:** a list of operations applied to the local Beads workspace. Each operation is one of:

| Operation | bd command | Effect |
|-----------|------------|--------|
| `comment` | `bd comments add <id> "<marker>\n<result | failed>: <summary>"` | Writes execution outcome as a comment on the bead; first line is the idempotency marker |
| `close` | `bd close <id> --reason "…"` | Closes the bead (success path only) |
| `update-metadata` | `bd update <id> --set-metadata key=value` | Updates `hermes_status` and `hermes_iteration` |

### Idempotency Requirements

Re-running `sync-results --apply` with the **same** results file **must not** produce duplicate
comments, duplicate state transitions, or broken invariants. This is enforced by an operation
marker embedded in every result comment.

**Requirement (implemented — v1.0.1+):**

```
Upon applying a result comment, the bridge writes a unique operation identifier
into the first line of the comment body so that a dry-run (or subsequent apply)
can detect that this result was already processed and skip it.

Format: hermes-beads-op: <bead_id>-<sha256_prefix>
```

The full op-id formula and re-run behavior are specified in §7. The high-level guarantees are:

1. **Re-running a success result** is a no-op: the op ID is detected in the existing comment, the
   bridge emits a `skipped` operation with reason `"already applied"`, and no `bd close` is
   issued. The bead stays closed exactly once.
2. **Re-running a failure result** is a no-op for the iteration counter: the op ID is detected,
   the bridge skips the result, and `hermes_iteration` is not incremented a second time.
3. **Mixed re-runs** (a results file where some records have been applied and some are new) apply
   only the new records; already-applied records are skipped.

Dry-run and apply use the same emission logic (`build_result_sync_operations`), so the
dry-run output exactly predicts the apply behavior, including the `"already applied"` skips.

### Comment Markers (Current)

The comment body for a result or failure begins with the marker line, followed by a
status line:

```
hermes-beads-op: <bead_id>-<sha256_prefix>
result: <summary>
```

```
hermes-beads-op: <bead_id>-<sha256_prefix>
failed: <summary>
```

The marker is the bridge's contract that the mutation has been applied. Downstream agents and
tooling that read result comments MUST treat the marker as the source of truth for "already
applied", not the comment text or close status alone (those can be set by other paths).

> **Format deviation from v1.0.1 reserved marker.** v1.0.1 reserved a `[op:sync-<bead-id>-<result-hash>-<seq>]`
> suffix on the same line as `result:` / `failed:`. The shipped format uses a separate
> `hermes-beads-op:` prefix line and omits the sequence number. This is an additive change
> (the `result:` / `failed:` prefix lines still parse the same), but consumers that grep for
> the literal `[op:sync-` pattern need to be updated.

## 3. Future Live Mutation Paths

### `hb bridge dispatch --apply` (Phase 4/5)

```
hb bridge dispatch --dry-run      # preview only — implemented
hb bridge dispatch --apply        # implemented for --backend local-file
```

**Current behavior:**
1. Read `bd ready --json` to find unblocked, open beads
2. Skip beads that already have `metadata.hermes_kanban_task_id`
3. For each remaining bead, create a dispatch artifact (local-file or Hermes Kanban task)
4. Write `metadata.hermes_kanban_task_id` (or equivalent) back to the bead

**Required idempotency rules:**

- A bead that already has `hermes_kanban_task_id` set MUST be skipped (no duplicate dispatch).
- If `hermes_status` is `in_progress` and the bead has a kanban task id, it MUST NOT be
  re-dispatched.
- Dry-run output MUST exactly match the planned mutations of `--apply` (one-to-one parity).
- When the local-file backend is active, dispatch writes handoff packets to the configured
  output directory. Re-running dispatch on the same set of ready beads MUST produce identical
  packets (content-addressable or skip-if-exists semantics).

### `hb bridge tick` (Phase 6)

```
hb bridge tick                    # NOT YET IMPLEMENTED
```

The bridge tick composes dispatch, sync-results, and Beads push into a single cron-friendly
command. Its mutation semantics are the union of the individual commands it runs. The tick
must be idempotent: if it is interrupted mid-way, re-running it must complete pending work
without duplicating completed work.

## 4. Dry-Run / Apply Parity

**The cardinal rule:** every mutating `hb bridge` command MUST have a `--dry-run` mode whose
output exactly predicts what the `--apply` mode will do.

```text
hb bridge dispatch --dry-run        → lists planned operations without executing
hb bridge dispatch --apply          → executes exactly those operations
hb bridge sync-results --dry-run    → lists planned bd operations
hb bridge sync-results --apply      → executes exactly those operations
```

### Parity Invariants

1. **One-to-one operation mapping**: every operation shown in dry-run output is executed in
   the same order during apply. No hidden operations, no conditional side effects.
2. **Deterministic output**: dry-run on the same input state produces the same output every
   time (modulo timestamps).
3. **No state read during apply**: the apply path must not re-read Beads state and branch on
   it. All decision-making happens in the dry-run / plan step; the apply step is a mechanical
   replay. This prevents skew between what dry-run predicted and what apply actually does.
4. **Error isolation**: if a single operation within apply fails, the remaining operations must
   still execute. Partial failure is acceptable; atomic rollback is not required.

### Deviations (Documented Exceptions)

| Command | Dry-run precision | Notes |
|---------|-------------------|-------|
| `sync-results --apply` | Exact | `build_result_sync_operations` produces the same list whether called from dry-run or apply. See `src/hermes_beads/cli.py`. |

## 5. Backend Boundaries

### Local-File Backend (Phase 4)

The local-file backend writes handoff packets to a local directory instead of calling Hermes
Kanban. It is the **test harness** for the bridge contract:

- No network dependencies
- No Hermes installation required
- Results are JSON files that `sync-results` can read back
- The entire loop (dispatch → execute → sync-results → close) can be tested in CI

The backend implementation lives in `src/hermes_beads/local_file_backend.py`.
It writes a deterministic JSON queue file with this shape:

```json
{
  "tasks": [
    {
      "id": "local-<sha256-prefix>",
      "status": "queued",
      "payload": { "source": "beads" }
    }
  ]
}
```

Task IDs are stable hashes of the canonical payload JSON. Re-creating the same
payload returns the same task ID and leaves the queue unchanged, so the local
queue can safely be used by future `dispatch --apply` dry-run/apply parity tests.
Relative queue-file paths are resolved against the project root supplied by the
caller; absolute paths are preserved.

**Boundary:** the local-file backend MUST implement the same operation interface as the Hermes
Kanban backend. Switching backends should be a configuration change, not a code change to
dispatch/sync logic. The backend is injected via a formal dispatch plan boundary:

- `DispatchOp` records describe the work to do (`create` or `skipped`).
- `build_dispatch_plan(...)` decides the operation list without mutating Beads, local files, or Hermes Kanban.
- A dispatch backend replays the planned `create` operations via `create(payload) -> task_id`.
- Optional `show(...)` and `complete(...)` methods let the same backend participate in result-sync flows, but dispatch planning does not call them.

`hb bridge dispatch --dry-run` currently uses this planner and prints planned create payloads only. `hb bridge dispatch --apply --backend local-file --queue-file <path>` replays the same plan into the deterministic JSON queue. Later backends must execute the same operation list that dry-run emitted; they must not re-plan against fresh Beads state and silently diverge from the preview.

### Hermes Kanban Backend (Phase 5)

The Hermes Kanban backend is the **production execution queue**:

- Creates Hermes Kanban tasks from ready beads
- Reads completed kanban task results and feeds them to `sync-results`
- Requires a running Hermes Agent with Kanban enabled
- All dispatch and sync operations remain gated by dry-run/apply parity

**Boundary:** the Kanban backend never becomes a source of truth. If Hermes is offline, beads
remain in Beads with `hermes_status: ready`. The bridge must not block on Hermes availability.

## 6. Public-Safety Boundary

All bridge output — dry-run previews, apply confirmations, handoff packets, dashboard views,
and cron reports — MUST be public-safe:

| Forbidden | Allowed |
|-----------|---------|
| Private network addresses (`private IPv4 ranges`) | Documentation-only placeholder ranges |
| API keys, tokens, PATs | Redacted placeholders (`<token>`) |
| Absolute user filesystem paths (`/<home>/…`, `C:\<Users>\…`) | Project-relative paths (`docs/…`) |
| Private VPN names or hostnames | Public hostnames (e.g., `github.com`) |
| Environment variable values | Variable names without values |
| Raw agent transcripts | Structured handoff packets |

Enforcement: `scripts/scan-privacy.sh` runs as a pre-commit and CI gate.

## 7. Result Operation IDs

> This section is the authoritative spec for the operation-id mechanism. It corresponds to
> the v1.0.1+ implementation in `src/hermes_beads/result_ops.py`. The earlier draft
> reserved a `[op:sync-<bead-id>-<result-hash>-<seq>]` suffix; see the deviation note in §2
> for the relationship between the reserved and shipped formats.

### Comment Markers

Every result-sync comment starts with a stable, unique operation identifier on its own line:

```
hermes-beads-op: <bead_id>-<sha256_prefix>
result: <summary>
```

```
hermes-beads-op: <bead_id>-<sha256_prefix>
failed: <summary>
```

The marker is parsed by the regex `hermes-beads-op:\s*(\S+)`, defined in
`src/hermes_beads/result_ops.py` (`_OP_MARKER_RE` / `parse_op_marker`). It tolerates any
non-whitespace token after the colon and matches on the first line of the comment, but the
bridge always emits the marker as the first line.

### Op ID Generation

The op ID is the bead ID, a hyphen, and the first 8 hex characters of SHA-256 over four
newline-joined fields:

```
op_id = "<bead_id>" + "-" + SHA-256(bead_id + "\n" + dispatch_id + "\n" + status + "\n" + summary)[:8]
```

| Field | Source | Notes |
|-------|--------|-------|
| `bead_id` | Result record's `bead_id` (or `source_bead_id` fallback) | E.g. `hb-abc` |
| `dispatch_id` | Result record's `dispatch_id` | Defaults to `"unknown"` if absent |
| `status` | Normalized status | `completed` for `completed` / `success` / `done`; `failed` otherwise |
| `summary` | Result record's `summary` | Free text, may be empty |

The separator between the four fields is a single literal newline character (`\n`, ASCII
0x0A). The 8-hex-character truncation is intentional: it gives 32 bits of collision space,
which is sufficient for the "already applied within one Beads workspace" check. The same
four inputs always produce the same op ID — the ID is a stable hash, not a random UUID.

The op ID is derived purely from the result record content, never from local file paths,
timestamps, or other non-public-safe inputs. This means the op ID can be re-computed from
the result file alone and matched against prior comments without re-running the bridge.

### Deduplication on Re-run

`build_result_sync_operations` accepts an optional `existing_comments` mapping (bead ID →
list of comment dicts). On every invocation, the bridge:

1. For each result record, computes the op ID from the formula above.
2. Scans the bead's existing comments and extracts any op IDs (using `parse_op_marker`).
3. If the freshly-computed op ID is already in the set of seen op IDs, the bridge emits
   a `skipped` operation with reason `"already applied"` and does not write a comment, close,
   or update-metadata operation for that record.
4. Otherwise, the bridge proceeds with the normal emission (comment + close for `completed`,
   comment + update-metadata for `failed`).

This makes re-running the same results file a true no-op: no duplicate comments, no
duplicate `bd close` calls, and no double-increment of `hermes_iteration`. A partial re-run
(where the file mixes new and old records) applies only the new records and skips the rest;
the two cases do not interfere.

### Why the Marker Lives in the Comment Body

The marker is a property of the **mutation**, not of the bead state. A `hermes_iteration`
counter or a `close` status can be set by other paths (manual `bd close`, a different
worker, an admin tool); the comment marker is the only signal the bridge owns end-to-end.
This is also why the bridge uses the marker rather than the close status for
"already applied" detection: close status can be set without the bridge having run.

### Breaking Change Note (Format Evolution)

The v1.0.1 contract reserved an `[op:sync-<bead-id>-<result-hash>-<seq>]` suffix on the
same line as the `result:` / `failed:` body. The shipped format uses a separate
`hermes-beads-op:` prefix line and does not include a sequence number. This is an additive
change to the comment body — the `result:` and `failed:` prefixes still parse identically —
but consumers that grep for the literal `[op:sync-` pattern need to be updated to match
`hermes-beads-op:` instead.

## 8. Roadmap Connection

The product contract phases align with the roadmap stages in [`ROADMAP.md`](roadmap.md):

| Phase | Document section | Implementation bead | Status |
|-------|-----------------|-------------------|--------|
| Phase 1 | This document | hb-ip5.2 | Done (v1.0.1) |
| Phase 2 | §5 Local-File Backend, §5 Hermes Kanban Backend | hb-ipx.x | Done (v1.0.1 — package + dry-run commands) |
| Phase 3 | §7 Result Operation IDs, §10 Retry Policy | hb-b88.4 (op-id) + hb-b88.8 (docs) | Done (v1.0.1+) |
| Phase 4 | §5 Local-File Backend dispatch path | hb-b88.x | Planned |
| Phase 5 | §5 Hermes Kanban Backend | hb-b88.x | Planned |
| Phase 6 | §3 Bridge Tick | hb-b88.x | Planned |

The Phase 3 work landed as: (a) `result_ops.py` exposing `build_op_id` and `parse_op_marker`,
(b) `cli.py` wiring the marker into the `comment` op body and reading prior comments for
dedup, (c) `tests/test_result_ops.py` covering the formula and the parser, and (d) the docs
you are reading now.

## 9. Non-Goals and Unsupported

### Non-Goals

- **Beads as orchestration engine.** Beads stores durable state and routing hints; it does not
  schedule agents, manage concurrency, or implement retry policies. The retry policy in §10
  is a comment-marker / iteration-counter contract enforced by the bridge; the *dispatch*
  retry decision itself remains the dispatcher's responsibility.
- **Distributed consensus.** The bridge runs in a single Hermes controller environment. There
  is no leader election, distributed locking, or consensus protocol.
- **Real-time synchronization.** The bridge operates on a polling model (Phase 6 default: every
  10 minutes). Sub-minute synchronization is not a goal.
- **Edit-in-place from dashboard.** Dashboards are read-only observability surfaces.
- **Cross-project Beads mesh.** The bridge operates on a single Beads workspace per hermes-beads
  installation.
- **Hermes Agent features.** The bridge does not replicate, cache, or proxy Hermes Agent
  capabilities (profile resolution, tool selection, model routing).

### Unsupported Operations

- **`hb bridge dispatch --apply`** without first having local-file and/or Hermes Kanban backend
  implementations (Phase 4 / Phase 5). Idempotency for dispatch is covered by the
  `hermes_kanban_task_id` rule in §3, independent of result-sync idempotency.
- **Live cron tick** without completing Phase 4 and Phase 5 (local and Hermes backends).
- **Cross-machine Beads sync** without explicit `bd dolt pull/push` — the bridge does not
  implement its own sync protocol.
- **Direct `.beads/issues.jsonl` manipulation** — hb commands read and write only through
  the `bd` CLI.

## 10. Retry Policy

The bridge defines a contract for how result records map to mutations of retry bookkeeping
on the bead. The contract is enforced by the `sync-results` apply path and is observable
through the comment marker, the `hermes_status` metadata field, and the `hermes_iteration`
counter.

### What Counts as a Retry

A "retry" is a second (or later) attempt to execute the same bead, triggered by a worker
failure. The contract makes this observable by:

- Incrementing `metadata.hermes_iteration` by exactly **one** per failed result record.
- Setting `metadata.hermes_status` to `failed` whenever a result record has `status: failed`.
- Closing the bead (status `completed`) on a success result record.

### Per-Result-Record Idempotency

A given `(bead_id, dispatch_id, status, summary)` tuple mutates the bead at most one time,
no matter how many times `sync-results --apply` is invoked with the same input. This is
guaranteed by the operation marker (§7):

- The first time a result record is applied, the bridge writes a comment whose first line is
  `hermes-beads-op: <op_id>`, then performs the close or update-metadata op.
- On every subsequent invocation, the bridge reads existing comments, finds the same op ID
  via `parse_op_marker`, and emits a `skipped` operation with reason `"already applied"`.
  The bead is **not** closed a second time, and `hermes_iteration` is **not** incremented a
  second time.

### Partial Re-runs

A result file can mix new and old records. The bridge applies only the new ones; old ones
are skipped independently. The dry-run output lists both kinds of operation, with the
`skipped` operations labelled with the reason, so operators can confirm before applying
that exactly the right records will be applied.

### Dispatch-Side Retry Decisions

The bridge does **not** decide when to retry. That is the dispatcher's responsibility,
and the only signal the bridge provides is `hermes_iteration` and `hermes_status`. The
recommended dispatcher policy is:

| `hermes_status` | `hermes_iteration` | Suggested action |
|-----------------|--------------------|------------------|
| absent or `ready` | 0 | First dispatch — no prior attempt. |
| `failed` | 1 | First retry — same bead, fresh worker. |
| `failed` | 2 | Second retry — consider escalation, profile change, or human review. |
| `failed` | ≥ 3 | Stop retrying automatically; require human review. |
| `in_progress` | any | Do not dispatch; an in-flight attempt exists. |
| `completed` | any | Bead is closed; no dispatch needed. |

These are recommendations, not contract — the bridge guarantees that `hermes_iteration`
and `hermes_status` are consistent with the comment marker, but it does not choose a
threshold for "too many retries". Dispatchers and operators are free to set their own
escalation policy.

### Failure Detection Boundary

The bridge treats any result record whose `status` is not `completed` / `success` / `done`
as a failure. It does not interpret error types, retryable vs. non-retryable classifications,
or transient vs. permanent causes. The `summary` field is the worker's only feedback channel
to the dispatcher, and the bridge preserves it verbatim in the comment.
