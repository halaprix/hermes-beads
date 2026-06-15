# Changelog

## [Unreleased]

### Changed

- **Refactor:** stripped cargo-cult packaging ceremony. Removed GitBook docs, PyPI publish workflow, docstring coverage gate, dry-run-only `gates` and `dashboard` modules, and unused helpers. Bridge surface (bd ↔ Hermes Kanban dispatch, result-sync idempotency, tick/cron) is unchanged. See `~/.hermes/plans/2026-06-15-hermes-beads-slim-down.md` for the rationale.
