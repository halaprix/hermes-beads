# Gate Resolver Architecture

## Overview

The gate resolver chooses the Hermes profile that should execute a bead. It is an adapter-layer concern: Beads stores durable project state and routing hints, while Hermes decides how to execute work.

The resolver must not turn Beads into an orchestration engine. Beads remains the source of truth for what needs to be done; Hermes remains responsible for who does it and when.

## Inputs

Allowed inputs:

- `metadata.hermes_profile` — explicit preferred profile
- `labels` — coarse task class such as `docs`, `bridge`, `testing`, `architecture`
- `issue_type` — `task`, `feature`, `bug`, `epic`, `chore`
- `priority` — used for ordering, not for model choice by itself
- Handoff packet fields derived from `bd show <id> --json`

Disallowed inputs:

- Private machine names
- Local filesystem paths
- API keys or credentials
- Hidden chat context from previous agents
- Provider-specific prompt hacks

## Outputs

The resolver produces:

```json
{
  "bead_id": "hb-xxx",
  "hermes_profile": "ts-dev",
  "reason": "explicit metadata.hermes_profile"
}
```

This profile is then copied into the Kanban dispatch payload as the assignee.

## Resolution Rules

1. If `metadata.hermes_profile` exists, use it.
2. If labels include `docs`, use `docs`.
3. If labels include `planning` or `architecture`, use `planner`.
4. Otherwise, default to `ts-dev`.

These rules are intentionally simple. More complex routing belongs in Hermes configuration, not in Beads metadata.

## Boundary With Beads

Beads should not contain:

- Model names
- Provider names
- API key references
- Local machine identifiers
- Runtime queue state beyond a link like `hermes_kanban_task_id`

Beads can contain stable public routing hints such as `hermes_profile` and labels.

## Anti-Patterns

- Do not encode full orchestration policy into Beads labels
- Do not infer execution profile from private context
- Do not use gates to bypass human approval
- Do not route tasks to a profile just because a previous agent used it
- Do not add new metadata fields without updating `docs/metadata-schema.md`

## Future Work

A future resolver may support Beads gates for human approval. That should be implemented as an explicit bridge step: list gates, ask the human, resolve the gate, then dispatch the newly unblocked bead.
