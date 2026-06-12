# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Compatibility matrix doc (`docs/beads-compatibility.md`) defining supported/unsupported Beads setup modes, minimum bd version, and the machine-readable bd output contract.
- Automated compatibility smoke tests covering standard embedded, stealth embedded, and nested cwd modes.
- Contract tests for fields hb consumes from `bd ready --json`, `bd show --json`, `bd comments --json`, and `bd context --json`.
- Stderr-warning capture tests that fail if bd --json commands emit deprecation/removal notices.

### Changed

- Rewrote ROADMAP.md from stale four-phase bootstrap plan to v1.0.1 product roadmap with ten phased stages, agy and Claude review conclusions, and explicit done/not-done status table.

### Deprecated

### Removed

### Fixed

### Security

## [1.0.1] - 2026-06-12

### Added

- Root `README.md` for package indexes and first-run CLI guidance
- PyPI package metadata: description, license, author, keywords, classifiers, and project URLs

### Changed

- Prepared release artifacts for package-index publication without moving the already-pushed `v1.0.0` tag

## [1.0.0] - 2026-06-12

### Added

- GitBook-compatible docs generation via `scripts/generate_gitbook_docs.py`
- CI checks for generated GitBook docs, non-editable package install, and code doc coverage above 90%
- Deterministic AST-based doc coverage gate via `scripts/check_doc_coverage.py`

### Changed

- Promoted the public bridge contract to `1.0.0`
- Handoff packets now use the same profile resolver as bridge dispatch when `metadata.hermes_profile` is absent

### Fixed

- Fixed installed CLI startup by loading version from package metadata instead of assuming a source-tree `VERSION` file exists
- Aligned bridge documentation with implemented `bd comments add` result sync commands
- Added profile-selection reasons to `hb bridge profile --dry-run` output

## [0.3.0] - 2026-06-12

### Added

- GitHub Actions CI for privacy scan and pytest
- Cross-machine Beads sync protocol documentation
- Gate resolver architecture documentation and dry-run profile selection
- Bridge cron polling documentation
- Project state dashboard specification
- Dry-run dispatch bridge: `hb bridge dispatch --dry-run`
- Result-sync bridge: `hb bridge sync-results --dry-run` and `--apply`
- Comment-backed handoff packets using `bd comments <id> --json`
- `hermes_iteration` retry tracking in result-sync operations
- End-to-end smoke test using a temporary Beads workspace

### Changed

- Tightened PR/release policy around one-bead-per-PR, mechanical release commits, and task-graph-only orchestration commits
- Updated privacy scanner to scan tracked files in CI while allowlisting files that intentionally document blocked patterns
- Updated `docs/kanban-bridge.md` from design-only phases to implemented dry-run commands

### Fixed

- Corrected handoff comment command documentation from `bd comment list` to `bd comments <id> --json`
- Fixed gate profile fallback so architecture-only beads route to `planner`

## [0.2.0] - 2026-06-12

### Added

- Metadata schema: `docs/metadata-schema.md` — execution fields, lifecycle states, reserved prefixes, handoff packet shape
- Handoff packet spec: `docs/handoff-packet.md` — required/optional fields, public-safe example, anti-patterns
- CLI skeleton: `src/hermes_beads/cli.py` — Click-based CLI with `--version`, `ready --dry-run`, `handoff --dry-run`
- Python package: `pyproject.toml`, `src/hermes_beads/`
- Tests: `tests/test_cli.py` — 4 tests covering all CLI commands
- Kanban bridge plan: `docs/kanban-bridge.md` — architecture, phases, API surface, error handling
- Release/tagging policy documented in `CONTRIBUTING.md` and `docs/pr-flow.md`

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [0.1.0] - 2026-06-12

### Added

- Initial project setup and governance documentation
- Public repository guardrails: LICENSE (MIT), .gitignore, SECURITY.md, docs/privacy.md
- Privacy scan script: `scripts/scan-privacy.sh`
- Beads task graph: 7 bootstrap tasks tracking project lifecycle
- Governance docs: CHANGELOG.md, VERSION, CONTRIBUTING.md, SECURITY.md, ROADMAP.md, docs/pr-flow.md
- PR template: `.github/pull_request_template.md`
- Beads usage guide: `docs/beads-usage.md`

### Changed

### Deprecated

### Removed

### Fixed

### Security
