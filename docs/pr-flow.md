# PR Flow

## Overview

All changes to hermes-beads go through pull requests. This document outlines the PR lifecycle, review requirements, and merge criteria.

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
