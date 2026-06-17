# Changelog

## [2.0.0-beta.1] — 2026-06-17

### Fixed

- **CI commitlint:** replaced `wagoid/commitlint-github-action@v6` (Docker Node 20, incompatible with GitHub Actions Node 24) with direct `npx @commitlint/cli` call.

## [2.0.0-alpha.2] — 2026-06-17

### Changed

- **Configurable scan roots:** project discovery now uses three-tier resolution
  (env var → config file → default `~/workspace`) instead of hardcoded paths.
  No code changes needed to add custom project directories.
- **Added `build` to dev dependencies** (fixes test failures on clean Python 3.12).
- **Version alignment:** manifest, pyproject, and changelog now agree on `2.0.0-alpha.2`.

## [2.0.0-alpha.1] — 2026-06-17

### Added

- **Dashboard plugin:** visual bead DAG with vis-network, neon glow theme,
  project selector, status filters, search, dispatch buttons, gate resolver,
  30s auto-refresh, keyboard shortcuts.
- `bead_model.py` — Pydantic models (Bead, BeadDependency, BeadGraph, etc.)
- `bead_reader.py` — JSONL parser with `discover_projects()` and `read_project_beads()`
- `graph_builder.py` — vis-network-compatible node/edge builder with status
  colours and priority-scaled sizing
- Plugin API endpoints: `/api/projects`, `/api/projects/<name>/beads`,
  `/api/projects/<name>/graph`, `/api/projects/<name>/dispatch`,
  `/api/projects/<name>/gate/<id>`

### Changed

- **Deprecated standalone `hb` CLI** — dashboard plugin is the primary interface
- **Synced repo rules** with leakwatch standard — `.commitlintrc.json`,
  `.editorconfig`, `.cspell.json`, issue templates, dependabot config,
  markdown-link-check config, upgraded privacy scanner
- Rewrote `AGENTS.md`, `CONTRIBUTING.md`, `PULL_REQUEST_TEMPLATE.md`
- Added `pydantic>=2.0` dependency, `[dev]` extras with `pytest>=8.0`
- Upgraded CI to multi-job gate (hygiene → test → docs → all-green)

### Removed

- `Makefile` (replaced by `python -m pytest`)
- `scripts/scan-privacy.sh` (replaced by `scripts/privacy-scan.sh` v2)
- Compiled `build/` artifacts

## [1.1.0a1]

### Changed

- **Refactor:** stripped cargo-cult packaging ceremony. Removed GitBook docs,
  PyPI publish workflow, docstring coverage gate, dry-run-only `gates` and
  `dashboard` modules, and unused helpers. Bridge surface (bd ↔ Hermes
  Kanban dispatch, result-sync idempotency, tick/cron) is unchanged.
