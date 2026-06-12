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
| `comment` | `bd comments add <id> "result: …"` | Writes execution outcome as a comment on the bead |
| `close` | `bd close <id> --reason "…"` | Closes the bead (success path only) |
| `update-metadata` | `bd update <id> --set-metadata key=value` | Updates `hermes_status` and `hermes_iteration` |

### Idempotency Requirements

Re-running `sync-results --apply` with the **same** results file **must not** produce duplicate
comments, duplicate state transitions, or broken invariants.

**Requirement (not yet implemented — Phase 3):**

```
Upon applying a result comment, the bridge writes a unique operation identifier
into the comment body so that a dry-run (or subsequent apply) can detect that this
result was already processed and skip it.

Format: result: <summary>  [op:sync-<bead-id>-<result-hash>-<seq>]
```

Until operation IDs are implemented, the contract is:

1. **Re-running a success result** creates a duplicate comment on the bead and a second
   `bd close` attempt. `bd close` on an already-closed bead may succeed silently or may emit a
   warning — this is backend-dependent and NOT guaranteed idempotent.
2. **Re-running a failure result** creates a duplicate failure comment and *increments
   `hermes_iteration` again*, which corrupts retry accounting.

**Therefore, `sync-results --apply` MUST NOT be called with the same results file more than
once until Phase 3 is implemented.** This is enforced by the roadmap ordering: Phase 3
(result-sync idempotency) must be complete before live dispatch (Phase 5) enables scenarios
where a single results file could be synced more than once.

### Comment Markers (Concept)

Even though operation IDs are not yet implemented, the contract reserves the following
comment-body conventions for future use:

- `result: <summary>` — success result from kanban execution
- `failed: <summary>` — failure result with error summary
- `result: <summary>  [op:sync-<bead-id>-<result-hash>-<seq>]` — future idempotent result marker
- `failed: <summary>  [op:sync-<bead-id>-<result-hash>-<seq>]` — future idempotent failure marker

The `[op:sync-<bead-id>-<result-hash>-<seq>]` suffix is the unique operation identifier. When it is absent (current
behavior), the bridge can only distinguish operations by the comment text itself, which is
ambiguous when the same result file is re-processed.

## 3. Future Live Mutation Paths

### `hb bridge dispatch --apply` (Phase 4/5)

```
hb bridge dispatch --dry-run      # preview only — implemented
hb bridge dispatch --apply        # NOT YET IMPLEMENTED
```

**Planned behavior:**
1. Read `bd ready --json` to find unblocked, open beads
2. For each ready bead, create a dispatch artifact (local-file or Hermes Kanban task)
3. Write `metadata.hermes_kanban_task_id` (or equivalent) back to the bead

**Required idempotency rules (before go-live):**

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

**Boundary:** the local-file backend MUST implement the same operation interface as the Hermes
Kanban backend. Switching backends should be a configuration change, not a code change to
dispatch/sync logic. The backend is injected via an abstraction (currently implicit in
`build_kanban_payload` + `build_result_sync_operations`; may become a formal plugin interface).

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

## 7. Result Operation IDs (Phase 3)

> This section defines the concept. Implementation is deferred to Phase 3 (see ROADMAP.md).

### Comment Markers

Each result-sync operation that writes a comment should include a stable, unique operation
identifier as a `[op:…]` suffix in the comment body:

```
result: Task completed successfully  [op:sync-20260612-abc123]
failed: Worker timed out              [op:sync-20260612-def456]
```

### Op ID Generation

The operation ID is generated from public-safe result content, never from local file paths:

- The bead ID
- The dispatch/task ID when present
- The normalized result status
- A hash of the normalized summary/body fields
- A monotonic sequence number within the parsed results payload when needed to break ties

Format: `[op:sync-<bead-id>-<result-hash>-<seq>]`

### Deduplication on Re-run

When `sync-results --apply` (or its dry-run equivalent) encounters an existing comment on the
target bead that contains a matching `[op:…]` suffix, it MUST skip that operation. This makes
re-running the same results file a true no-op.

### Ambiguity Without Op IDs

Without operation IDs (current v1.0.1 behavior), the bridge has no reliable way to tell
whether a given result was already processed. Comment body matching is fragile because the
`summary` text may vary between runs, and multiple comments with identical bodies are valid
(e.g., two different workers both succeeded on the same task type).

### Breaking Change Warning

Adding operation IDs to comment bodies changes the comment format. Any downstream tooling that
parses result comments by body text alone must be updated to ignore the `[op:…]` suffix. The
change is additive: `[op:…]` is appended to the existing body format, so simple string matching
against `result:` and `failed:` prefixes still works.

## 8. Roadmap Connection

The product contract phases align with the roadmap stages in [`ROADMAP.md`](roadmap.md):

| Phase | Document section | Implementation bead | Status |
|-------|-----------------|-------------------|--------|
| Phase 1 | This document | hb-ip5.2 | Current |
| Phase 3 | §7 Result Operation IDs | hb-ipx.x | Planned |
| Phase 4 | §5 Local-File Backend | hb-ipx.x | Planned |
| Phase 5 | §5 Hermes Kanban Backend | hb-ipx.x | Planned |
| Phase 6 | §3 Bridge Tick | hb-ipx.x | Planned |

## 9. Non-Goals and Unsupported

### Non-Goals

- **Beads as orchestration engine.** Beads stores durable state and routing hints; it does not
  schedule agents, manage concurrency, or implement retry policies.
- **Distributed consensus.** The bridge runs in a single Hermes controller environment. There is
  no leader election, distributed locking, or consensus protocol.
- **Real-time synchronization.** The bridge operates on a polling model (Phase 6 default: every
  10 minutes). Sub-minute synchronization is not a goal.
- **Edit-in-place from dashboard.** Dashboards are read-only observability surfaces.
- **Cross-project Beads mesh.** The bridge operates on a single Beads workspace per hermes-beads
  installation.
- **Hermes Agent features.** The bridge does not replicate, cache, or proxy Hermes Agent
  capabilities (profile resolution, tool selection, model routing).

### Unsupported Operations

- **`hb bridge dispatch --apply`** without completing Phase 3 first (result-sync idempotency).
- **Live cron tick** without completing Phase 4 and Phase 5 (local and Hermes backends).
- **Cross-machine Beads sync** without explicit `bd dolt pull/push` — the bridge does not
  implement its own sync protocol.
- **Direct `.beads/issues.jsonl` manipulation** — hb commands read and write only through
  the `bd` CLI.
