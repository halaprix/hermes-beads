# Hermes-Beads Metadata Schema

This document defines the public metadata contract for hermes-beads. The schema is intentionally narrow: it covers durable operational state for disposable agents, not generic agent memory or arbitrary key-value storage.

## Design Principles

1. **Narrow scope** — only fields that enable agent handoff and execution routing
2. **Public-safe** — no private IPs, tokens, machine IDs, or internal paths
3. **Stable** — fields are additive only; no breaking changes within a major version
4. **Agent-readable** — designed for programmatic parsing via `bd show --json`

## Metadata Fields

All fields live under the `metadata` key on a Beads issue. Agents MUST NOT write arbitrary keys outside this schema.

### Execution Fields

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `hermes_status` | string | `ready`, `in_progress`, `blocked`, `complete`, `failed` | Execution state of this task |
| `hermes_profile` | string | Hermes profile name (e.g., `ts-dev`, `docs`, `planner`) | Recommended Hermes profile for this task |
| `hermes_mode` | string | `pr`, `manual` | Whether this task requires PR flow or manual verification |
| `hermes_created_by` | string | agent identifier | Which agent created this bead (optional) |
| `hermes_stop_condition` | string | free text | What constitutes done — acceptance criteria summary (optional) |
| `hermes_kanban_task_id` | string | kanban task ID | Link to Hermes Kanban task when bridge is active (optional) |
| `hermes_iteration` | integer | non-negative | Number of times this task has been attempted (optional) |

### Lifecycle States

```
open → in_progress → complete
           ↓
        blocked → in_progress (when unblocked)
           ↓
        failed → in_progress (retry)
```

| State | Meaning |
|-------|---------|
| `open` | Work not yet started; task is in the ready queue |
| `in_progress` | An agent has claimed this task and is actively working |
| `blocked` | Task has unresolved blockers; no agent should work on it |
| `complete` | Task is done; merged/landed |
| `failed` | Agent gave up or timed out; task is stalled |

Transitions:
- `open` → `in_progress`: agent runs `bd update <id> --claim`
- `in_progress` → `blocked`: agent runs `bd comment <id> "blocked: <reason>"` then updates status
- `blocked` → `in_progress`: blockers resolved, agent re-claims
- `in_progress` → `complete`: agent runs `bd close <id> --reason "done"`
- `in_progress` → `failed`: agent abandons or times out; iteration counter increments

### Reserved Field Prefixes

Fields prefixed with `hermes_` are reserved by this schema. Agents MAY read any `hermes_` field. Agents MAY write only the fields listed above. All other metadata keys are ignored by the bridge.

### Anti-Patterns

- Do NOT store arbitrary JSON blobs in `hermes_notes` or similar catch-all fields
- Do NOT use `hermes_` prefix for non-schema fields
- Do NOT use `metadata` for agent memory — use `bd remember` for persistent knowledge
- Do NOT store file paths, IPs, or tokens in any metadata field

## Handoff Packet

When a Hermes worker picks up a bead, it receives a handoff packet constructed from the bead's data. The packet is the authoritative context for the worker — it replaces whatever the previous agent's context window contained.

### Packet Construction

The orchestrating agent (or bridge) builds the packet by reading:

```
bd show <id> --json
```

And extracting:

1. `id` — bead identifier
2. `title` — what to do
3. `description` — why it exists and what needs to be done
4. `metadata.hermes_stop_condition` — stop condition (if set)
5. `metadata.hermes_profile` — which profile to use
6. `metadata.hermes_mode` — pr or manual
7. Comments (via `bd comment list <id>`) — decisions, blockers, handoff notes

### Packet Shape (JSON)

```json
{
  "bead_id": "hb-xxx",
  "goal": "Title of the task",
  "description": "Full description from the bead",
  "stop_condition": "What 'done' looks like",
  "hermes_profile": "recommended profile",
  "hermes_mode": "pr | manual",
  "dependencies": [
    { "id": "hb-yyy", "title": "Blocking task title", "status": "open | closed" }
  ],
  "comments": [
    { "author": "agent-name", "body": "decision or blocker note", "created_at": "ISO8601" }
  ],
  "iteration": 0
}
```

### Public-Safe Example

```json
{
  "bead_id": "hb-xxx",
  "goal": "Add minimal dry-run CLI skeleton",
  "description": "Create a Python CLI with --version, ready --dry-run, and handoff --dry-run. No live Hermes dispatch.",
  "stop_condition": "CLI responds to --version with correct output; dry-run commands print expected JSON without side effects",
  "hermes_profile": "ts-dev",
  "hermes_mode": "pr",
  "dependencies": [
    { "id": "hb-hh3", "title": "Define Hermes-Beads metadata schema", "status": "closed" },
    { "id": "hb-lpy", "title": "Specify the Beads-generated handoff packet", "status": "closed" }
  ],
  "comments": [
    { "author": "halaprix", "body": "decision: use Click for CLI framework", "created_at": "2026-06-12T12:00:00Z" }
  ],
  "iteration": 0
}
```

## Schema Versioning

The schema version is implicit in the `VERSION` file at the repo root. Breaking changes increment the major version. Additive changes (new fields) increment the minor version and are backward-compatible.

Current schema: `1.0` (matches VERSION `0.2.0`)
