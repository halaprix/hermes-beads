# Contributing

Thank you for your interest in contributing to hermes-beads.

This is a single-user bridge for one maintainer. Changes land on `main` directly
after running `pytest -x -q` to confirm all gates pass.

## Getting Started

1. Clone the repository
2. Run `bd init --prefix hb` to set up the beads workspace with the `hb` prefix
3. Use `bd create`, `bd ready`, `bd update`, and `bd close` for task management

## Development Setup

The project uses [beads](https://github.com/gastownhall/beads) for issue tracking. All work is tracked via beads issues rather than external task managers.

## Making Changes

1. Make changes on `main` (this project is single-user)
2. Run `pytest -x -q` before committing
3. Keep commits atomic and self-contained

## Code Style

- Follow existing code patterns in the repository
- Commit messages should explain the *why*, not just the *what*

## Reporting Issues

- Use beads to report issues: `bd create` to open a new issue
- Include the beads ID (`hb-XXX`) in any related PRs
