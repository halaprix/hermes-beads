# Release Matrix

> Where hermes-beads artifacts ship, in what order, and what gates guard each distribution phase.
> Last updated: 2026-06-14.

## Overview

hermes-beads publishes to four distribution targets, sequenced to minimise user-facing instability
and ensure every artifact is verified before reaching the next tier.

| Target | Artifact | Purpose | Status |
|--------|----------|---------|--------|
| GitHub Release | Source tarball + signed tag | Pre-PyPI distribution; changelog-anchored milestone marker | **Done** — v1.0.1 |
| Local alpha artifacts | `hermes-beads` wheel + sdist | Release-candidate package smoke before package-index upload | **Done locally** — v1.1.0a1 build/twine/wheel smoke |
| TestPyPI | `hermes-beads` wheel + sdist | Canary — verify packaging, metadata, and `pip install` before public PyPI | Blocked on Trusted Publishing/credentials |
| PyPI | `hermes-beads` wheel + sdist | Public package index — `pip install hermes-beads` | Blocked on TestPyPI success + Trusted Publishing/credentials |
| Hermes Agent upstream | `hermes-beads` skill SKILL.md + entry | Upstream Hermes Agent skill — enables `hermes-beads` as a first-party Hermes capability | Prepared locally; waits for publish/signoff |

## Sequencing Constraints

```text
GitHub Release ──> TestPyPI ──> PyPI ──> Hermes Agent upstream
     ^                ^           ^               ^
     |                |           |               |
  v1.0.1 done     Phase 8.1   Phase 8.2      Phase 8.3
```

1. **GitHub Release** must exist before any PyPI publication (the GitHub release tag is the
   source-of-truth marker).
2. **TestPyPI** must pass before real PyPI — install smoke test and metadata review on TestPyPI
   is mandatory.
3. **PyPI** must be stable before the Hermes Agent upstream skill PR is opened — the skill
   references the published package, so unrevertable PyPI publication is a prerequisite.
4. **Hermes Agent upstream** is the final step: after the PyPI artifact is stable and the package
   has been exercised in real workflows (local-file dispatch, Phase 4), the upstream PR can be
   prepared.

## GitHub Release / Local Alpha

**Done:** [v1.0.1](https://github.com/halaprix/hermes-beads/releases/tag/v1.0.1)

`v1.1.0a1` is prepared in this branch as local wheel/sdist artifacts. It is not considered
published until TestPyPI and PyPI package-index upload/install smokes pass.

What ships:
- Source archive (GitHub auto-archive from tag)
- Signed tag (`git tag -s v1.0.1`)
- Changelog entry covering all changes since v1.0.0
- CI check results published as release check annotations

**Gate:** all CI checks pass, CHANGELOG.md updated, VERSION bumped, tag pushed, release created
on GitHub.

## TestPyPI (Phase 8.1)

**Purpose:** Validate packaging metadata, dependency resolution, and `pip install` behaviour
without affecting the public PyPI index.

### Automated vs Manual

| Step | Automation | Trigger |
|------|-----------|---------|
| Build wheel + sdist | CI (GitHub Actions) | On tag push matching `v*` |
| Publish to TestPyPI | CI (GitHub Actions) | Same workflow, after build |
| Smoke install `pip install --index-url https://test.pypi.org/simple/ hermes-beads` | CI | Same workflow |
| Metadata review (description renders correctly, classifiers correct, project URLs work) | Manual | Developer checks TestPyPI project page |

### Trusted Publishing / Credential Requirements

- Preferred: GitHub environment `testpypi` configured for PyPI Trusted Publishing/OIDC.
- Fallback: environment-scoped TestPyPI API token stored as a secret, never committed.

### Gate Checklist

Before a TestPyPI publish is considered successful, ALL of the following must pass:

1. [ ] Wheel and sdist build without errors
2. [ ] `pip install` succeeds from TestPyPI in a clean virtualenv
3. [ ] `hb --version` reports the correct version after install
4. [ ] Package metadata (description, author, license, classifiers) renders correctly on the
      TestPyPI project page
5. [ ] Project URLs on TestPyPI (`Source`, `Issues`, `Changelog`) resolve correctly
6. [ ] Privacy scan passes on the release commit

## PyPI (Phase 8.2)

**When:** After TestPyPI verification passes and all pre-PyPI gates are green (see below).

### Trusted Publishing / Credential Requirements

- Preferred: GitHub environment `pypi` configured for PyPI Trusted Publishing/OIDC.
- Fallback: project-scoped PyPI API token stored as an environment-scoped secret, never committed.

### Automated Publish Flow

```text
Tag push v* ──> Build wheel + sdist ──> Publish to TestPyPI ──> Manual verify ──>
    └─> Trigger PyPI publish (workflow_dispatch, requires maintainer approval)
    └─> Build wheel + sdist ──> Publish to PyPI ──> Create GitHub Release
```

The publish workflow is split into two phases:

1. **TestPyPI publish** runs automatically on tag push.
2. **PyPI publish** is a manual `workflow_dispatch` that requires a maintainer to verify the
   TestPyPI result first.

CI never publishes to both TestPyPI and PyPI in a single workflow run — always a two-step process.

### Pre-PyPI Gate Checklist

These gates MUST pass before any real PyPI publication. They are checked by CI on the release
commit and must be verified manually before triggering the `workflow_dispatch` PyPI job.

| # | Gate | Enforcement | Failure action |
|---|------|-------------|----------------|
| 1 | **Privacy scan** | `scripts/scan-privacy.sh` in CI | Block release — fix exposed data first |
| 2 | **pytest** | `python -m pytest -q` in CI | Block release — fix failing tests |
| 3 | **Doc coverage** | `python scripts/check_doc_coverage.py --threshold 0.9` in CI | Block release — add missing docstrings |
| 4 | **Clean install smoke test** | CI workflow that creates a venv, `pip install` from built wheel, runs `hb --version` | Block release — fix packaging |
| 5 | **TestPyPI verification** | Successful TestPyPI publish + manual metadata review | Block release — fix metadata or publish workflow |
| 6 | **GitBook docs checked** | `python scripts/generate_gitbook_docs.py --check` in CI | Block release — regenerate stale docs |
| 7 | **CHANGELOG.md updated** | Release commit must move `[Unreleased]` entries into the version heading, leaving `[Unreleased]` ready for subsequent changes | Maintainer responsibility |

### Pre-PyPI Gate — Local Developer Workflow

Before cutting a release, a developer runs:

```bash
bash scripts/scan-privacy.sh
python scripts/generate_gitbook_docs.py --check
python scripts/check_doc_coverage.py --threshold 0.9
python -m pytest -q
```

All four commands must exit 0 before the release tag is pushed.

## Hermes Agent Upstream Skill (Phase 8.3)

**When:** After the PyPI artifact is stable and the package has been exercised in real workflows
(see ROADMAP.md Phase 4).

### What Ships

- `skills/hermes-beads/SKILL.md` — skill definition that references the PyPI-published package
- Optional: supporting references, templates, or scripts under `skills/hermes-beads/`
- Hermes Agent `skills/` directory entry in the hermes-beads repository (not the Hermes monorepo)

### How — Upstream Contribution Path

1. The `hermes-beads` skill is authored in the hermes-beads repository first.
2. A PR is opened against the [Hermes Agent skills repository](https://github.com/nousresearch/hermes)
   adding the skill directory.
3. The PR references the stable PyPI version in `requirements.txt` or SKILL.md.
4. The upstream PR is opened only after:
   - TestPyPI and PyPI publications are complete
   - The local-file dispatch backend (Phase 4) has been exercised with a no-gap smoke loop
   - At least one real bead has been dispatched through the bridge

### Files to Contribute

| File | Contents |
|------|----------|
| `skills/hermes-beads/SKILL.md` | Skill frontmatter (name, description, category), install instructions citing `pip install hermes-beads`, usage examples |
| `skills/hermes-beads/references/api.md` | (Optional) API surface for the hermes-beads CLI commands relevant to Hermes users |

## Versioning Policy

hermes-beads follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

| Component | Policy |
|-----------|--------|
| **MAJOR** | Breaking changes to the public CLI (`hb …`) interface or the bridge contract (handoff packet shape, dry-run/apply semantics). |
| **MINOR** | New features that maintain backward compatibility (new CLI subcommands, new dispatch backends, new non-breaking metadata fields). |
| **PATCH** | Bug fixes, documentation improvements, CI-only changes, internal refactoring with no public API change. |

### Tag Discipline

- Tags MUST be signed (`git tag -s`) with a GPG key.
- Tag format: `v<major>.<minor>.<patch>` (e.g. `v1.0.1`).
- Tags are pushed only after CI passes and the release commit is on `main`.
- Once pushed, a tag is NEVER deleted or overwritten. If a release is broken, the fix gets a new
  PATCH version.

### Changelog Requirements

- Every release MUST have an entry in `CHANGELOG.md` under the release version heading.
- The `[Unreleased]` section accumulates changes between releases.
- Changelog format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## What "Done" Means for Each Distribution Phase

| Phase | Done criteria |
|-------|---------------|
| **GitHub Release** | Tag pushed, release created on GitHub, CHANGELOG.md formatted for release |
| **TestPyPI** | Wheel + sdist published to TestPyPI, `pip install` smoke passes in CI, metadata reviewed by a maintainer |
| **PyPI** | Wheel + sdist published to PyPI, `pip install hermes-beads` works from a clean environment, GitHub Release created with PyPI links |
| **Hermes Agent upstream** | Hermes Agent skill PR merged or ready for review, skill references published PyPI version, smoke test passes using the upstream skill |

## Roadmap Connection

The distribution phases are defined in [`ROADMAP.md`](roadmap.md) Phase 8. The sequencing
constraints in this document are enforced by the roadmap ordering:

- Phase 2 (v1.0.1 GitHub Release) ✓ done
- Phase 3 (result-sync idempotency) — must precede live dispatch
- Phase 4 (local-file dispatch) — must precede Hermes upstream PR
- Phase 8 (distribution) — three sub-phases as documented above

See also:
- [`docs/product-contract.md`](product-contract.md) — authority model, mutation semantics, dry-run/apply parity
- [`docs/beads-compatibility.md`](beads-compatibility.md) — supported bd setup modes and output contract
