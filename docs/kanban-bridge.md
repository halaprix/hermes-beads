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

## Privacy and Security

- Handoff packets must not contain private IPs, tokens, or machine paths
- Only public-safe metadata fields are copied into Kanban task bodies
- The bridge runs in the Hermes controller environment, not on worker machines

## Future Considerations

- **Gate-based dispatch** — use Beads gate resolution to decide which profile handles a bead
- **Parallel worker coordination** — multiple workers picking from the same Beads queue
- **DoltHub sync** — cross-machine Beads state (currently uses local embedded Dolt)
