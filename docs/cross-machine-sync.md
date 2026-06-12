# Cross-Machine Beads Sync Protocol

## Overview

hermes-beads uses Beads as the durable task graph. Beads stores canonical issue state in its local Dolt database and can sync that state through the git remote under `refs/dolt/data`. The JSONL export is useful for review, but it is not the source of truth.

This document defines the public-safe operating protocol for multiple Hermes agents or machines sharing the same bead graph.

## Source of Truth

- **Canonical task state:** Beads embedded Dolt database
- **Sync transport:** `bd dolt push` / `bd dolt pull`
- **Code transport:** normal git branches, pull requests, and tags
- **Passive export:** `.beads/issues.jsonl`

Do not use `.beads/issues.jsonl` as the wire protocol. It is an export for humans and code review.

## Session Start Checklist

Every agent session starts with:

```bash
git checkout main
git pull --rebase
bd dolt pull
bd prime
bd ready
```

If `bd dolt pull` fails, stop and inspect the error. Do not start work from stale bead state.

## Claiming Work

Before editing files:

```bash
bd show <id>
bd update <id> --claim
```

The claim is an intent signal. It does not replace git branches or PRs. Code changes still happen on feature branches.

## Session End Checklist

Every worker session ends with:

```bash
python -m pytest tests/ -v
bash scripts/scan-privacy.sh
git status
bd close <id> --reason "done"
bd dolt push
git push
```

If the worker cannot complete the task, it must add a comment instead of closing:

```bash
bd comment <id> "blocked: <reason, next step, evidence>"
bd dolt push
```

## Conflict Expectations

Conflicts can happen in two layers:

1. **Git code conflicts** — resolved through normal branch rebase/merge
2. **Beads state conflicts** — resolved by pulling Beads state and replaying the intended issue update

Safe recovery pattern:

```bash
bd dolt pull
bd show <id>
# repeat the intended bd update/comment/close if still valid
bd dolt push
```

Do not manually edit the embedded Dolt database or import JSONL during normal operation.

## Orchestrator Rules

The orchestrator is responsible for:

- Choosing which ready beads to dispatch
- Avoiding parallel dispatch of tasks likely to touch the same files
- Verifying worker claims against actual git diffs and tests
- Merging PRs
- Closing beads only after the work is merged or otherwise accepted

Workers are responsible for:

- Working from a single bead-generated handoff packet
- Keeping changes scoped to the bead
- Recording blockers and decisions as Beads comments
- Never leaking private context into public files or metadata

## Anti-Patterns

- Do not start from `bd ready` without first syncing
- Do not use `.beads/issues.jsonl` as the authoritative state
- Do not run `bd import` as part of normal collaboration
- Do not close a bead based only on an agent summary; verify the diff
- Do not store secrets, local paths, hostnames, or private IPs in comments or metadata
