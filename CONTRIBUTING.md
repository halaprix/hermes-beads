# Contributing to hermes-beads

First off: thank you. hermes-beads bridges Beads task state into Hermes Agent workflows, and every issue, PR, and bug report helps.

> **TL;DR:** Conventional Commits, one logical change per commit, push after every commit, and read `AGENTS.md` if you're an LLM coding agent.

---

## Code of Conduct

Be excellent to each other. Respectful, constructive communication only.

---

## What we welcome

- 🐛 **Bug reports** — open an issue with reproduction steps.
- 💡 **Feature requests** — open an issue first; let's discuss before you build.
- 📖 **Docs improvements** — typos, clarifications, examples all welcome.
- 🔧 **Pull requests** — bug fixes, refactors, new features (after discussion).

## What needs a heads-up first

- **Large refactors** — open an issue, link the design doc, get sign-off.
- **New dispatch backends** — discuss the integration approach before implementation.
- **Any payment-related code** — out of scope, do not propose.
- **Home Assistant / smart-home integration** — out of scope.

---

## Development Setup

### Prerequisites

| Tool | Version | Why |
|---|---|---|
| Python | 3.10+ | Runtime |
| pip | latest | Package install |
| Git | 2.40+ | Conventional commit hooks |
| Beads CLI (`bd`) | latest | Task tracking for this project |

### Cloning

```bash
git clone https://github.com/halaprix/hermes-beads
cd hermes-beads
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

---

## Git Workflow

### 1. Branch

Branch from `main`:

```bash
git checkout -b feat/<short-kebab-name>
git checkout -b fix/<issue-number>-<short-kebab-name>
git checkout -b docs/<topic>
git checkout -b chore/<topic>
```

### 2. Commit

**Conventional Commits are mandatory.** Format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

| Type | Use for |
|---|---|
| `feat` | New user-visible feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no code change |
| `refactor` | Code change, no behavior change |
| `perf` | Performance improvement |
| `test` | Adding or fixing tests |
| `build` | Build system / dependency changes |
| `ci` | CI / GitHub Actions changes |
| `chore` | Tooling, scaffolding, housekeeping |
| `revert` | Reverting a previous commit |

**Scope examples:** `cli`, `plugin`, `dashboard`, `dispatch`, `sync`, `ci`, `docs`.

**Subject:** imperative, lowercase, no period, max 72 chars. Example: `feat(cli): add dispatch backend selector`.

**Body:** wrap at 100 chars, explain *what* and *why* (not *how*). Reference the bead: `Refs hb-dv1.` or `Closes hb-dv1.`.

### 3. One logical change per commit

Do not batch unrelated fixes. If your PR has two independent fixes, split into two commits (and ideally two PRs).

### 4. Push after every commit

Marian reads diffs, not the working tree. Push as you go.

### 5. Open a PR

Open a PR against `main`. Fill in the PR template. **Wait for review from at least one other human or a different LLM agent** than the one that wrote the change.

---

## Commit Message Examples

### Good ✅

```
feat(cli): add dispatch backend selector

Introduces --backend flag to hb dispatch, supporting local-file
and hermes-kanban backends. Picks up backend config from
~/.hermes/config.yaml by default.

Closes hb-dv1.
```

```
fix(sync): handle empty bead list without crashing

Beads sync was failing when a workspace had zero open beads.
Added a guard clause and unit test.

Fixes hb-ab3.
```

### Bad ❌

```
fixed stuff
```

```
WIP feat(cli) dispatch backend (also fixed a typo in README,
bumped deps, and changed log format — will clean up later)
```

---

## Coding Style

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/) with 100-char line limit.
- Type hints on public API boundaries.
- One class per module unless tightly coupled.
- Tests live in `tests/`, mirroring `src/hermes_beads/` structure.
- Run `python -m pytest tests/ -v` before committing.

### Imports

- Wildcard imports: ❌
- Group: stdlib → third-party → first-party, blank line between.

---

## Testing

| Layer | Tool | Run |
|---|---|---|
| Unit | pytest | `python -m pytest tests/ -v` |
| CLI smoke | pytest (subprocess) | `python -m pytest tests/test_cli.py -v` |

---

## Versioning & Releases

We follow [SemVer 2.0.0](https://semver.org/). Tags: `vMAJOR.MINOR.PATCH`, always `v`-prefixed.

- Until `v2.0.0`: breaking changes are allowed in `MINOR` bumps (pre-2.0 convention).
- After `v2.0.0`: breaking changes bump `MAJOR`.
- Every release updates `CHANGELOG.md` with the `Added / Changed / Fixed / Removed` sections.
- Releases are cut by Marian.

---

## Reporting Bugs

Use the [Bug Report](./.github/ISSUE_TEMPLATE/bug_report.yml) template. Include:

- hermes-beads version (`hb --version`)
- Python version (`python --version`)
- OS and distro
- Reproduction steps
- Expected vs actual
- Error messages / stack traces (sanitised — no private paths or tokens!)

---

## Security Issues

**Do not file a public issue for security bugs.** Email `security@halaprix.dev` or use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability).

---

## License

By contributing, you agree that your contributions are licensed under the [MIT License](./LICENSE), the same as the project.

---

## Questions?

Open a [Feature Request](./.github/ISSUE_TEMPLATE/feature_request.yml) or ask in the relevant PR. Keep the answers in public so others can find them.

Thanks for contributing.
