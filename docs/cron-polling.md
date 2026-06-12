# Bridge Cron Polling

## Overview

The bridge can run as a periodic Hermes cron job once dispatch and result-sync commands are live. The cron job should be conservative: collect state, run dry-run checks first, then execute only explicitly enabled live operations.

## Loop

A bridge polling tick performs:

1. Sync local code and Beads state
2. Dispatch newly ready beads to Hermes Kanban
3. Sync completed or failed Kanban results back to Beads
4. Push Beads state
5. Stay quiet if nothing changed

## Safe Schedule

Recommended initial schedule:

```text
every 10m
```

The job should not schedule other cron jobs. Recursive scheduling is prohibited.

## Dry-Run First

Before enabling live mode, run:

```bash
hb bridge dispatch --dry-run
hb bridge sync-results --dry-run --results-file /path/to/results.json
```

Live mode should only be enabled after these dry-runs produce expected operations.

## Failure Behavior

- If Beads sync fails: stop the tick and report the sync error
- If dispatch fails: leave the bead open and comment the error when safe
- If result sync fails: leave the Kanban task open so the next tick can retry
- If privacy scan fails: do not push or dispatch

## Privacy Rules

Cron output delivered to chat must be concise and public-safe. Do not include:

- Environment variables
- Tokens
- Local filesystem paths beyond project-relative paths
- Private network addresses
- Raw agent transcripts

## Example Prompt

A future Hermes cron prompt can be:

```text
In the hermes-beads repo, run the bridge tick: sync Beads state, dispatch ready beads, sync completed Kanban results, push Beads state. Stay silent if there is nothing to report. Never create cron jobs from inside this run.
```

## Open Questions

- Whether live dispatch should be enabled by default or require a config flag
- How often result sync should retry failed workers
- Whether Telegram notifications should be sent only for failures or also for new dispatches
