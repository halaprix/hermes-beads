# Changelog

## Unreleased

### Fixed

- **Graph showed only a fraction of the project.** `build_graph` and
  `build_graph_raw` dropped every dependency whose type was not `blocks`,
  which hides the whole epic structure — on a real 479-bead store that meant
  119 of 453 relationships drawn, with all 274 `parent-child` edges missing.
  All types are now rendered, each with its own colour and dash pattern, and
  edges carry their `type` so a frontend can filter per type. Pass
  `edge_types={"blocks"}` for the previous execution-constraint-only view.
- **Phantom nodes from cross-project references.** A dependency pointing at a
  bead outside the current project is now dropped instead of making
  vis-network materialise a node for the unknown endpoint.
- Added `plugin/plugin.yaml` and documented `hermes plugins enable hermes-beads`
  so the dashboard tab appears under Hermes versions that require explicit
  opt-in for user plugins.
- Added FastAPI and HTTPX test-client dependencies so plugin API tests pass in
  a clean CI environment.
- Installed and PATH-detected the Beads CLI in CI before tests that exercise
  real `bd` calls.
- Updated stale Beads sync documentation links that were breaking the docs gate.

### Added

- **Dolt-backed workspaces are readable.** Current Beads stores issues in Dolt
  and no longer writes `.beads/issues.jsonl` unless the workspace opts in to
  `export.auto`, so the reader saw an empty project. It now falls back to
  `bd -C <dir> export` when the file is absent, and discovery qualifies a
  workspace on the `.beads/` directory rather than on `issues.jsonl`. An
  existing `issues.jsonl` still takes precedence, so nothing gets slower.
  Memories are never requested — plain `bd export` omits them, and they can
  hold sensitive agent context.
- Documented the proposed standalone `hb serve` path for non-Hermes users.

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
