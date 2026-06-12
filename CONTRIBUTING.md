# Contributing

Thank you for your interest in contributing to hermes-beads.

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
