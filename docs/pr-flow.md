# PR Flow

## Overview

All changes to hermes-beads go through pull requests. This document outlines the PR lifecycle, review requirements, merge criteria, and release process.

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

### PR-Only After v0.1.0

After the v0.1.0 bootstrap tag, every change to `main` must arrive through a pull request. Direct commits to `main` are prohibited except for:
- Merging PR branches
- Applying reviewed hotfixes

## PR Lifecycle

1. **Branch Creation**: Create a feature branch from `main`
   - Branch naming: `feature/description` or `feat/beads-N`
2. **Development**: Make changes, commit using [Conventional Commits](https://www.conventionalcommits.org/)
3. **PR Submission**: Open a PR with the required template fields completed
4. **Review**: Address reviewer feedback
5. **Merge**: After all criteria are met

## Review Requirements

- Two-reviewer minimum for user-facing changes
- One reviewer sufficient for internal/chore changes
- All CI checks must pass before review

## Merge Criteria

- [ ] PR template fully completed (description, testing notes, breaking changes)
- [ ] All CI passes:
  - Privacy scan (no internal URLs, private IPs, or tokens)
  - Lint checks
- [ ] Required reviewers approved
- [ ] No unresolved review comments

## Hotfixes

For urgent fixes:

1. Create a branch: `hotfix/description`
2. Get expedited review
3. Merge directly to `main`
4. Apply same quality standards as regular PRs
