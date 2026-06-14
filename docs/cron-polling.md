# Bridge Cron Polling

## Overview

`hb bridge tick` is the cron-friendly bridge controller. It plans dispatch and result-sync work, applies it only when explicitly requested, uses a lockfile to avoid overlapping runs, and can stay silent on no-op ticks.

## Commands

```bash
hb bridge tick --dry-run
hb bridge tick --apply --backend local-file --queue-file .hermes-beads/dispatch.json
hb bridge tick --apply --backend hermes-cli
```

Useful safety flags:

```bash
--lock-file .hermes-beads/tick.lock
--stale-after 3600
--privacy-scan
--git-pull
--git-push
--bd-pull
--bd-push
--silent-noop
```

## Tick order

A live tick performs the following sequence:

1. acquire lock, replacing it only if stale
2. run optional privacy/git/Beads preflight sync
3. dispatch ready, unlinked beads through the selected backend
4. sync result records when `--results-file` is supplied
5. run optional Beads/git push
6. release lock
7. print a public-safe summary unless `--silent-noop` suppresses empty work

## Dry-run output

Dry-run emits only operation counts and public backend names. It never prints environment values, private paths, tokens, raw comments, or raw worker logs.

```json
{
  "operations": [
    {"op": "dispatch", "count": 1, "backend": "local-file", "path": ".hermes-beads/dispatch.json"}
  ],
  "summary": {
    "applied": false,
    "noop": false,
    "dispatch_count": 1,
    "result_count": 0,
    "backend": "local-file"
  }
}
```

## No-op policy

Cron should usually use `--silent-noop`. When no ready beads and no result records exist, `hb bridge tick --dry-run --silent-noop` and `hb bridge tick --apply --silent-noop` emit no stdout.

## Failure behavior

- held non-stale lock: exit non-zero before mutation
- stale lock: replace and continue
- privacy scan failure: exit before dispatch
- git/Beads pull failure: exit before dispatch
- dispatch create failure: exit and leave Beads unchanged
- post-create show failure: keep the Beads link/status mutation and return minimal task output
- result-sync duplicate: emit `skipped` via the existing operation marker rules

## Recommended Hermes cron prompt

```text
In the hermes-beads repository, run one bridge tick with `hb bridge tick --apply --backend local-file --queue-file .hermes-beads/dispatch.json --privacy-scan --silent-noop`. If the command produces output, summarize only the public-safe counts and failures. Do not create or modify cron jobs from inside this run.
```

## Schedule

Start conservative:

```text
every 10m
```

Increase frequency only after the local-file backend and result-sync paths have passed repeated smoke tests.
