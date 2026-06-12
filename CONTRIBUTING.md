# Contributing

Thank you for your interest in contributing to hermes-beads.

## Versioning and Tagging Policy

This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Each release is a clean, tagged commit.** Commits on `main` between tags are development work — not releases. The tag marks the stable surface area at that point in time.

### Release Protocol

1. Work on feature branches, commit cleanly to `main`
2. When a coherent set of changes is ready, tag the current commit:
   ```bash
   git tag -a v0.2.0 -m "v0.2.0: feature description"
   git push origin v0.2.0
   ```
3. Update `CHANGELOG.md` with the release date and contents
4. Update `VERSION` file to match the new version
5. **After the initial v0.1.0 tag, all new features go through pull requests**

### PR-Only After v0.1.0

After the v0.1.0 bootstrap tag, every product/code/documentation change to `main` must arrive through a pull request. Direct commits to `main` are prohibited except for:
- Merging or rebasing approved PR branches
- Applying reviewed hotfixes
- Maintainer-only mechanical release commits that update only `VERSION`, `CHANGELOG.md`, and tags
- Task-graph-only orchestration commits that update `.beads/issues.jsonl` without changing product files

When practical, keep one bead per PR. If several tightly coupled beads must share a PR, keep one commit per bead and explain the grouping in the PR body.

## Getting Started

1. Clone the repository
2. Run `bd init --prefix hb` to set up the beads workspace with the `hb` prefix
3. Use `bd create`, `bd ready`, `bd update`, and `bd close` for task management

## Development Setup

The project uses [beads](https://github.com/gastownhall/beads) for issue tracking. All work is tracked via beads issues rather than external task managers.

## Making Changes

1. Create a branch for your changes: `git checkout -b feature/description` or `feat/beads-N`
2. Make your changes following the code style guidelines
3. All changes go through the pull request process

## Pull Request Process

1. Fork the repository and create a feature branch
2. Ensure CI passes (privacy scan, lint)
3. Submit a PR with the required template fields completed
4. Two-reviewer minimum for user-facing changes
5. See [docs/pr-flow.md](docs/pr-flow.md) for full PR lifecycle details

## Code Style

- Follow existing code patterns in the repository
- Commit messages must use [Conventional Commits](https://www.conventionalcommits.org/):
  - `feat:` for new features
  - `fix:` for bug fixes
  - `docs:` for documentation changes
  - `chore:` for maintenance tasks

## Reporting Issues

- Use beads to report issues: `bd create` to open a new issue
- Include the beads ID (`hb-XXX`) in any related PRs
- See [docs/privacy.md](docs/privacy.md) for how we handle sensitive information

## Build in Public

This is a public project. All content must be public-safe:
- No internal URLs
- No private IP addresses
- No tokens, secrets, or credentials
