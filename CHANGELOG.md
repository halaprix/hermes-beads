# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- Governance docs: CHANGELOG.md, VERSION, CONTRIBUTING.md, ROADMAP.md, docs/pr-flow.md
- PR template: `.github/pull_request_template.md`
- Beads usage guide: `docs/beads-usage.md`

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security
