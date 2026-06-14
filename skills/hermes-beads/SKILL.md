---
name: hermes-beads
description: Use Beads as durable project state for Hermes Agent workers. Covers bd init/prime, hb bridge dispatch, result sync, tick, dashboard, gates, and release workflow.
---

# Hermes-Beads

Hermes-Beads connects Beads task state to Hermes Agent workflows.

## Install

```bash
pip install hermes-beads
```

The target project must also have the Beads CLI available:

```bash
bd version
```

## Common workflow

```bash
bd init --prefix demo --quiet
bd prime
hb bridge dispatch --dry-run
hb bridge dispatch --apply --backend local-file --queue-file .hermes-beads/dispatch.json
hb bridge sync-results --dry-run --results-file results.json
```

## Hermes Kanban backend

Use the real Hermes backend only after dry-run inspection:

```bash
hb bridge dispatch --apply --backend hermes-cli
```

The backend shells out to `hermes kanban create --json` and writes `metadata.hermes_kanban_task_id` back to Beads after successful creation.

## Cron tick

```bash
hb bridge tick --dry-run
hb bridge tick --apply --backend local-file --queue-file .hermes-beads/dispatch.json --privacy-scan --silent-noop
```

Use `--silent-noop` for cron jobs so unchanged projects stay quiet.

## Dashboard and gates

```bash
hb dashboard build --output dashboard.html
hb gates list --dry-run
hb gates approve <bead-id> --dry-run
```

The dashboard is read-only. Gate approval is dry-run only in this release.

## Pitfalls

- Beads is the source of truth; local queue files and dashboards are derived artifacts.
- Run `bash scripts/scan-privacy.sh` before publishing examples or docs.
- `metadata.hermes_kanban_task_id` is the dispatch dedupe key after Beads linkage succeeds.
- Hermes CLI dispatch also passes `--idempotency-key <bead-id>` to cover create-success/link-failure retries.
- `bd dolt push` may report that no remote is configured; the tracked JSONL export is still enough for public repo review.
