# Changelog

## [Unreleased]

### Changed

- **Chore:** synced repo rules with leakwatch standard — added `.commitlintrc.json`, `.editorconfig`, `.cspell.json`, issue templates, dependabot config, markdown-link-check config, and upgraded privacy scanner to allowlist-based v2. Rewrote `AGENTS.md` with full rules (privacy, git workflow, SemVer, code review, build-in-public etiquette, coding agent specifics, subagent discipline). Rewrote `CONTRIBUTING.md` with detailed PR workflow and commit message examples. Rewrote `PULL_REQUEST_TEMPLATE.md` with checklist-based format. Added `[dev]` extras to `pyproject.toml`.

- **Refactor:** stripped cargo-cult packaging ceremony. Removed GitBook docs, PyPI publish workflow, docstring coverage gate, dry-run-only `gates` and `dashboard` modules, and unused helpers. Bridge surface (bd ↔ Hermes Kanban dispatch, result-sync idempotency, tick/cron) is unchanged. See `~/.hermes/plans/2026-06-15-hermes-beads-slim-down.md` for the rationale.
