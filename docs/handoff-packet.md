# Beads-Generated Handoff Packet

## Overview

A handoff packet is the structured context a Hermes worker receives when it picks up a bead. It replaces the previous agent's context window entirely. The packet is constructed by reading the bead's data via `bd show <id> --json` and extracting a defined set of fields.

## Packet Construction

The orchestrating agent (or Hermes Kanban bridge) builds the packet by reading the bead's full data and composing it into a JSON object. Fields come from: bead title, description, metadata, and comments.

## Required Fields

- `bead_id`: string — the Beads issue identifier (e.g., hb-xxx)
- `goal`: string — the task title (what to do)
- `description`: string — full description from the bead (why it exists, what needs to be done)
- `hermes_profile`: string — recommended Hermes profile (e.g., ts-dev, docs, planner)
- `hermes_mode`: string — pr or manual

## Optional Fields

- `stop_condition`: string — what 'done' looks like (from metadata.hermes_stop_condition)
- `dependencies`: array — list of blocking beads with their id, title, and status
- `comments`: array — decisions, blockers, and handoff notes from the comment thread
- `iteration`: integer — number of times this task has been attempted

## Public-Safe Example

```json
{
  "bead_id": "hb-as6",
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

## Anti-Patterns

- Do NOT include private IPs, tokens, file paths, or machine names in any field
- Do NOT use the handoff packet as a general-purpose memory store
- Do NOT store sensitive context across agents — use Beads comments for decisions, not secrets
- Do NOT modify the packet shape without updating docs/metadata-schema.md
