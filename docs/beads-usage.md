# Beads Usage Guide

## Overview

hermes-beads uses Beads (bd CLI) as the durable project task graph. All work is tracked as Beads issues, not markdown TODO files or kanban boards.

## Why Beads

Provides durable project state that survives context compaction. When an agent dies, the next agent can `bd prime` and `bd ready` to resume exactly where the previous agent left off — with full dependency graph, decisions recorded, and acceptance criteria intact.

## Session Workflow

1. At session start: `bd doll pull` (or `bd dolt pull` if Dolt sync is configured) then `bd prime`
2. Check `bd ready` for available tasks
3. Claim a task: `bd update <id> --claim`
4. Work on the task
5. Before committing: `bd dolt pull`, then close the bead: `bd close <id> --reason "done"`
6. Git commit + push

## Task Lifecycle

- **Open** (unstarted)
- **In Progress** (claimed by an agent)
- **Open** (completed, awaiting review or merge)
- **Closed** (merged/landed)

## Handoff Protocol

When transferring work between agents:

1. Writer agent: runs `bd show <id>` to capture full task state
2. Writer: adds a comment `bd comment <id> "handoff: [brief summary of what was done, blockers, next steps]"`
3. Reader agent: runs `bd dolt pull` then `bd prime` then `bd show <id>` to see full context
4. Reader: claims the bead and continues

## Anti-Patterns

- Do NOT use markdown TODO lists or separate kanban files — they fragment state
- Do NOT treat `.beads/issues.jsonl` as source of truth — it's an export; the Dolt DB is authoritative
- Do NOT run `bd init` inside the repo more than once
- Do NOT skip `bd dolt pull` before starting — you may work on stale state

## Metadata Convention

hermes-beads uses public metadata fields on beads to signal execution hints:

- `hermes_status`: `ready` | `in_progress` | `blocked`
- `hermes_profile`: the recommended Hermes profile for this task (e.g., `ts-dev`, `docs`, `planner`)
- `hermes_mode`: `pr` | `manual` (whether this task needs PR flow or manual verification)