# Roadmap

## Overview

hermes-beads bridges [Beads](https://github.com/gastownhall/beads) (a durable Dolt-backed task
graph) into Hermes Agent workflows. The project is at **v1.0.1** (GitHub release only — PyPI and
Hermes Agent upstream not yet published). This roadmap sequences remaining work based on review
feedback from agy and Claude.

> **Review conclusions (applied to this plan):**
> - agy: build and verify the local dispatch harness before wiring live/cron/dashboard/distribution.
> - Claude (initial pass): failed under incomplete third-party env; succeeded once extraneous
>   env vars were unset. Key correction: **result-sync idempotency must be implemented before
>   live dispatch is enabled**, because `hb bridge sync-results --apply` already mutates Beads
>   and re-running it must be safe.

## Sequencing

```
Phase 0 ── Preflight compatibility gate (done)
Phase 1 ── Product contract & roadmap docs (current)
Phase 2 ── Installed package + bd preflight (v1.0.1 done)
Phase 3 ── Result-sync idempotency — before live dispatch
Phase 4 ── Local-file dispatch backend & temp-product smoke loop
Phase 5 ── Hermes Kanban backend (after local proves the contract)
Phase 6 ── Bridge tick / cron controller
Phase 7 ── Read-only observability dashboard
Phase 8 ── Distribution: TestPyPI → PyPI → Hermes Agent upstream skill PR
Phase 9 ── Advanced gates / human approval
```

---

## Phase 0 — Preflight Compatibility Gate ✓ (done)

> Beads setup modes and bd JSON output contract are defined and tested.

The compatibility matrix in [`docs/beads-compatibility.md`](docs/beads-compatibility.md)
catalogues supported/unsupported setup topologies, minimum bd version (1.0.0), and
machine-readable output contract fields for `bd ready`, `show`, `comments`, and `context`.
Automated smoke and contract tests live in `tests/test_compatibility.py`.

**Phase gate:** matrix doc written, all 16 compatibility tests passing.

---

## Phase 1 — Product Contract & Roadmap Docs (in progress)

> Freeze the product contract before adding new live mutation paths.

- **hb-ip5.1** · Update ROADMAP.md to v1.0.1 product roadmap (this document)
- **hb-ip5.2** · Add product contract doc for bridge authority and apply semantics
- **hb-ip5.3** · Document release matrix and pre-PyPI gates
- **hb-ip5.4** · Regenerate GitBook docs and add roadmap docs to navigation
- **hb-ip5.6** · Beads setup compatibility matrix _(done — see Phase 0)_

**Phase gate:** all child tasks closed; product-contract doc merged; docs generation passes.

---

## Phase 2 — Installed Package + bd Preflight ✓ (done as v1.0.1)

> Released as [`v1.0.1`](https://github.com/halaprix/hermes-beads/releases/tag/v1.0.1)
> on GitHub. PyPI and Hermes Agent upstream are deferred to Phase 8.

What shipped in v1.0.1:

- Root `README.md` for package indexes and first-run CLI guidance
- PyPI package metadata (description, license, author, classifiers, project URLs)
- Public `hb` CLI skeleton with `--version` and dry-run commands
- Non-editable install smoke test in CI

**What is NOT shipped (deferred):** PyPI publication, Hermes Agent upstream PR, live dispatch.

---

## Phase 3 — Result-Sync Idempotency

> Before live dispatch touches Beads or Hermes Kanban, make `hb bridge sync-results --apply`
> safe to run repeatedly. Claude review identified this as the critical ordering constraint.

- Add operation IDs to result-sync records so re-running with the same file is a no-op
- Write idempotency contract tests that re-sync the same results file and assert no duplicate
  comments/state changes
- Dry-run should always match apply preview exactly

**Phase gate:** idempotency contract tests pass; re-running `sync-results --apply` with the same
results file produces no new state mutations.

---

## Phase 4 — Local-File Dispatch Backend & Temp-Product Smoke Loop

> agy review: prove the contract end-to-end with a local harness before wiring real backends.

- Implement a local-file dispatch backend that writes handoff packets to a local directory
  instead of calling Hermes Kanban
- End-to-end smoke test that creates a temporary Beads workspace, runs dispatch dry-run + apply,
  runs result-sync dry-run + apply, and closes the bead
- The temp-product smoke loop is the go/no-go gate for Phase 5

**Phase gate:** temp-product smoke loop passes end-to-end (dispatch → execute → sync-results → close)
using the local-file backend only.

---

## Phase 5 — Hermes Kanban Backend

> Only after the local backend proves the bridge contract (Phase 4 passes).

- Implement the real Hermes Kanban dispatch backend: `hb bridge dispatch` creates Hermes Kanban
  tasks from ready beads
- Wire `hermes_kanban_task_id` back into bead metadata
- All dispatch operations remain gated by dry-run/apply parity
- Idempotency rules from Phase 3 apply to the Kanban backend too

**Phase gate:** `hb bridge dispatch --dry-run` and `--apply` work against a real Hermes Kanban
instance, with the local backend test suite re-run and passing.

---

## Phase 6 — Bridge Tick / Cron Controller

> Compose sync, dispatch, result-sync, and push into a conservative scheduled bridge tick.

- Hermes cron job runs `hb bridge tick` on a configurable schedule (default: every 10m)
- Each tick: pull Beads → dispatch ready beads → sync completed results → push Beads
- Stay quiet when nothing changed
- Recursive cron scheduling prohibited (see `docs/cron-polling.md`)

**Phase gate:** cron job runs silently with no changes detected; when work is injected, the tick
dispatches and syncs correctly.

---

## Phase 7 — Read-Only Observability Dashboard

> Derive state from Beads and bridge dry-runs; never become a second source of truth.

- Show ready, running, blocked, failed, and closed beads
- Show bridge health: last dispatch/sync times, pending operations
- Show Hermes profile assignments per bead
- Debug view with raw public-safe packet data (see `docs/dashboard.md`)

**Phase gate:** dashboard renders correctly from `bd ready --json` data; all views use the
derive-only rule (no mutations, no stored dashboard state).

---

## Phase 8 — Distribution

> Publish only after local product smoke passes twice (Phase 4 and Phase 5).

Steps (sequenced):

1. **TestPyPI** — automated publish to TestPyPI from CI; verify install works
2. **PyPI** — public PyPI release after TestPyPI verification
3. **Hermes Agent upstream skill PR** — contribute `hermes-beads` integration as a Hermes Agent
   skill only after PyPI artifact is stable

**Phase gate:** `pip install hermes-beads` works from PyPI; Hermes Agent upstream PR is merged
or ready for review.

---

## Phase 9 — Advanced Gates / Human Approval

> Approval gates, retry escalation, reviewer routing — after the basic bridge loop is boring.

- Explicit stop/go gates between phases
- Retry escalation: after N failures, escalate to human review
- Reviewer routing: route failed beads to specific Hermes profiles

**Phase gate:** all child tasks closed; phase gate document defines the escalation policy.

---

## Done / Not Done Summary

| Item | Status |
|------|--------|
| v1.0.1 GitHub release | ✓ Done |
| PyPI publication | — Not done (Phase 8) |
| Hermes Agent upstream skill PR | — Not done (Phase 8) |
| Compatibility matrix (docs + tests) | ✓ Done |
| Product contract doc | — In progress |
| Result-sync idempotency | — Not done (Phase 3) |
| Local-file dispatch backend | — Not done (Phase 4) |
| Temp-product smoke loop | — Not done (Phase 4) |
| Hermes Kanban backend | — Not done (Phase 5) |
| Bridge tick / cron controller | — Not done (Phase 6) |
| Dashboard | — Not done (Phase 7) |
| Advanced gates / human approval | — Not done (Phase 9) |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get involved. All changes go through pull
requests and are tracked via beads issues (`hb-XXX`).
