# Roadmap

## Current state

hermes-beads is now at **v1.1.0a1** in this branch. The local bridge roadmap is implemented and locally verified:

- result-sync idempotency
- local-file dispatch backend and temp-product smoke loop
- real Hermes Kanban CLI backend and live smoke documentation
- cron-friendly `hb bridge tick`
- read-only static dashboard
- advanced gate metadata, retry escalation, and reviewer routing
- Trusted Publishing workflow and in-repository Hermes skill draft

Package-index publication remains externally gated: TestPyPI and PyPI require configured Trusted Publishing environments or package-index credentials. Those publication beads are intentionally blocked rather than falsely closed.

## Sequencing

```text
Phase 0 ── Preflight compatibility gate ✓
Phase 1 ── Product contract & roadmap docs ✓
Phase 2 ── Installed package + bd preflight ✓ v1.0.1
Phase 3 ── Result-sync idempotency ✓
Phase 4 ── Local-file dispatch backend & temp-product smoke loop ✓
Phase 5 ── Hermes Kanban backend ✓
Phase 6 ── Bridge tick / cron controller ✓
Phase 7 ── Read-only observability dashboard ✓
Phase 8 ── Distribution: TestPyPI → PyPI → Hermes Agent upstream skill PR ⚠ externally gated
Phase 9 ── Advanced gates / human approval ✓
```

## Implemented phases

### Phase 0 — Preflight Compatibility Gate

Beads setup modes and bd JSON output contract are defined in [`docs/beads-compatibility.md`](beads-compatibility.md) and tested in `tests/test_compatibility.py`.

### Phase 1 — Product Contract & Roadmap Docs

The bridge authority model, mutation semantics, public-safety rules, release matrix, and GitBook navigation are documented and generated docs are checked in CI.

### Phase 2 — Installed Package + bd Preflight

`v1.0.1` shipped the installable package baseline, CLI skeleton, package metadata, and non-editable install smoke. `v1.1.0a1` extends that package surface with the completed bridge commands.

### Phase 3 — Result-Sync Idempotency

`hb bridge sync-results` writes stable `hermes-beads-op:` markers and re-running the same results file is a no-op. Failure result records increment `hermes_iteration` at most once per unique result.

### Phase 4 — Local-File Dispatch Backend

`hb bridge dispatch --apply --backend local-file` writes deterministic queue records, links beads, gates dispatched beads to `in_progress`, and is covered by integration smoke tests.

### Phase 5 — Hermes Kanban Backend

`hb bridge dispatch --apply --backend hermes-cli` creates Hermes Kanban tasks using `hermes kanban create`, writes `metadata.hermes_kanban_task_id`, uses `idempotency_key=<bead_id>`, and treats post-create `show` failure as best-effort enrichment rather than retryable mutation failure.

### Phase 6 — Bridge Tick / Cron Controller

`hb bridge tick` composes optional privacy/git/Beads preflight sync, dispatch, result-sync, optional push, lockfile protection, stale-lock recovery, public-safe summaries, and silent no-op output.

### Phase 7 — Read-Only Observability Dashboard

`hb dashboard build` renders public-safe static HTML from Beads issue data. The dashboard is derived, read-only, and not a control plane.

### Phase 9 — Advanced Gates / Human Approval

`hb gates list --dry-run`, `hb gates approve <bead-id> --dry-run`, retry escalation metadata, and reviewer routing for PR-gated tasks are implemented. Approval mutation remains deliberately dry-run only in this release.

## Phase 8 — Distribution status

Implemented:

- `.github/workflows/publish.yml` builds, checks, and publishes through GitHub Trusted Publishing environments
- [`docs/release-publishing.md`](release-publishing.md) documents TestPyPI-first flow, PyPI manual dispatch, clean install smoke, rollback, and upstream-skill sequencing
- `skills/hermes-beads/SKILL.md` is prepared in-repo
- local build, `twine check`, and clean wheel install smoke pass for `1.1.0a1`

Blocked externally:

- TestPyPI upload and install smoke require TestPyPI Trusted Publishing or credentials
- PyPI upload requires successful TestPyPI verification plus PyPI Trusted Publishing or credentials
- Hermes Agent upstream PR should wait until the PyPI artifact is stable or receive explicit maintainer approval to proceed earlier

## Done / Not Done Summary

| Item | Status |
|------|--------|
| v1.0.1 GitHub release | ✓ Done |
| v1.1.0a1 local package artifacts | ✓ Done |
| Compatibility matrix | ✓ Done |
| Product contract doc | ✓ Done |
| Result-sync idempotency | ✓ Done |
| Local-file dispatch backend | ✓ Done |
| Temp-product smoke loop | ✓ Done |
| Hermes Kanban backend | ✓ Done |
| Bridge tick / cron controller | ✓ Done |
| Dashboard | ✓ Done |
| Advanced gates / human approval dry-runs | ✓ Done |
| Trusted Publishing workflow/docs | ✓ Done |
| TestPyPI publication | ⚠ Blocked on external package-index config/credentials |
| PyPI publication | ⚠ Blocked on TestPyPI success + external package-index config/credentials |
| Hermes Agent upstream skill PR | ⚠ Prepared locally; upstream PR waits for publish/signoff |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Work is tracked through Beads issues and GitHub PRs; release operations must pass the documented gates before publishing.
