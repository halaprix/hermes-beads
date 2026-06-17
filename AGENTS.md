# AGENTS.md — Operating Rules for Coding Agents

> **Audience:** Any LLM-based coding agent (Claude Code, Codex, Grok Build, Hermes subagents, etc.) working in this repository on behalf of `halaprix`. Read this first; treat it as binding.

---

## 1. Project Context

**hermes-beads** bridges [Beads](https://github.com/gastownhall/beads) task state into Hermes Agent workflows. It provides the `hb` CLI and will evolve into a Hermes plugin with a vis-network DAG dashboard rendering bead dependency graphs with clickable dispatch.

The project's hard constraint is **idempotency** — dispatch, sync, and result-claim operations must be safe to retry without double-dispatching or double-counting.

---

## 2. Ground Rules (NON-NEGOTIABLE)

### 2.1 Privacy & Disclosure

This is a **public, build-in-public** repository under the `halaprix` organisation.

**Allowed in commits, issues, PRs, comments, releases:**

- Project name (`hermes-beads`), repo name (`halaprix/hermes-beads`)
- Public dependency names and versions
- Generic stack mentions (e.g. "uses vis-network for DAG rendering")
- Architecture diagrams and code snippets
- Links to public Beads / Hermes documentation

**PROHIBITED — must never be disclosed in any artifact (including issues, PR comments, commits, release notes, generated docs):**

- Internal/private IP addresses (e.g. `192.168.x.x`, `10.x.x.x`, `172.16-31.x.x`)
- Filesystem paths under `/home/pkl/...` or any other user's home
- API keys, tokens, environment variable values (`.env` file contents)
- Home Assistant entities, devices, or any other smart-home internal state
- Names of other `halaprix/*` private repos unless they are already public
- Any reference to Marian's personal infrastructure (PC hostname, RTX 5070 Ti, etc.)
- Tailscale hostnames (e.g. `*.ts.net`)

**Rule of thumb:** if a fact would be useful to an attacker profiling Marian's home lab, it's not in this repo. Keep the public surface narrow.

### 2.2 No Payments / No Smart-Home Side Effects

- **Never** invoke payment flows, payment SDKs, or any code that touches money.
- **Never** read or write Home Assistant state from this project.
- **Never** commit credentials, even "test" ones. Use environment variables and `.env.example` only.

### 2.3 Git Workflow

- **One logical change per commit.** Do not batch unrelated fixes.
- **Conventional Commits** are mandatory. Format: `<type>(<scope>): <subject>`
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`
  - Example: `feat(cli): add dispatch backend selector`
- **Commit body** must reference the issue or design doc it implements when one exists.
- **Push after every commit.** Do not accumulate local commits — Marian reads diffs, not the working tree.
- **Never force-push to `main`.** Branches may be rebased; `main` is sacred.
- **Commit author:** the configured git identity, not a co-authored-by LLM line.

### 2.4 Semantic Versioning

- This project follows [SemVer 2.0.0](https://semver.org/). Tags: `vMAJOR.MINOR.PATCH`, prefixed with `v`.
- `MAJOR`: breaking API or data-format change.
- `MINOR`: backwards-compatible feature.
- `PATCH`: backwards-compatible bugfix.
- Pre-release: `v1.0.0-alpha.1`, `v1.0.0-beta.1`, `v2.0.0-rc.1`.
- **Until `v2.0.0` is released, breaking changes are allowed in `MINOR` bumps** (pre-2.0 SemVer convention).

### 2.5 Code Review

All non-trivial changes must be reviewed by **at least one** of:

- A second human reviewer, OR
- A different LLM agent from the approved set (Claude, Codex, Grok Build)

If a coding agent writes a feature, the same agent must not be the sole reviewer of its own output. Either Marian reviews, or a different agent does.

### 2.6 Build-in-Public Etiquette

- The README and PR template are the public face. Keep them sharp.
- Screenshot and demo paths in markdown should be relative (`./docs/screenshots/...`) — no absolute paths.
- If a feature is intentionally undocumented in public (e.g. a private dispatch backend), say so in the code comment and do not mention it in public docs.
- **Update docs on every relevant change.** If a commit adds, removes, or changes behaviour visible to users or contributors, update the corresponding doc file (`README.md`, `CHANGELOG.md`, `docs/*.md`) in the same PR — docs are not a separate cleanup step. When in doubt, update.

---

## 3. Repository Layout

```
hermes-beads/
├── AGENTS.md                   # this file
├── README.md                   # public-facing project readme
├── CHANGELOG.md                # keep-a-changelog format
├── CONTRIBUTING.md             # contribution guide
├── LICENSE                     # MIT (see §6)
├── pyproject.toml              # Python package metadata
├── .gitignore
├── .editorconfig
├── .commitlintrc.json
├── .cspell.json
├── .github/
│   ├── workflows/
│   │   └── ci.yml              # lint + test + privacy + spellcheck
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml
│   │   └── feature_request.yml
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── dependabot.yml
│   └── markdown-link-check.json
├── src/
│   └── hermes_beads/           # Python package
├── tests/                      # pytest
├── docs/                       # architecture, usage guides
└── scripts/                    # CI and maintenance scripts
```

---

## 4. Coding Agent Specifics

### 4.1 Tooling Expectations

- **Read this file** (`AGENTS.md`) and `README.md` before any action. If you cannot read both, say so and stop.
- **Use `bd` for task tracking.** Run `bd prime` for full workflow context.
- **Use `execute_code` or `terminal`** for filesystem work, not `cat` / `sed` / `awk` (Hermes convention).
- **Verify with real tool output.** Do not claim a file was written without `read_file`-ing it back. Do not claim a build passed without its exit code.
- **Run tests before committing:** `python -m pytest tests/ -v`

### 4.2 Subagent Discipline

- **Subagent cap = 600s.** If a subagent is still running at 600s, kill it and resume inline.
- **Multi-file refactors** with delegation: expect 10–20% leftover. Finish inline; do not re-dispatch the same task.
- **Do not poll.** Either the user is waiting (foreground) or you backgrounded with `notify_on_complete=true`. Do not `process(action='poll')` in a tight loop.
- **No "ready to push when you are" prompts.** Push when done.

### 4.3 Forbidden Patterns

- ❌ Inventing APIs, version numbers, or repo URLs that do not exist. If you don't know, say "I need to verify this" and use a search tool.
- ❌ Fabricating test output, build logs, or screenshots.
- ❌ Committing `.env`, secrets, or private key material.
- ❌ Lying about what changed in a PR. The diff is the source of truth.

### 4.4 Recommended Patterns

- ✅ Read the failing test before fixing it.
- ✅ Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists.
- ✅ Run `bd prime` for detailed command reference and session close protocol.
- ✅ When in doubt, ask. The cost of one clarifying question is lower than the cost of a wrong implementation.

---

## 5. Communication Style

- **Direct, no fluff.** Marian runs ADHD-friendly. Short sentences, bullet points, action items.
- **Markdown always.** Tables for comparisons, code blocks for code, lists for steps.
- **Polish / English mix OK in chat.** Repository artifacts (commits, docs, code comments) are **English only** unless explicitly localised.

---

## 6. Licensing

Default license for this project is **MIT License**, consistent with the Beads project it bridges. If a contributor wants a different license, raise it in an issue first; do not change `LICENSE` unilaterally.

---

## 7. Change Log for this File

| Date | Change | Author |
|---|---|---|
| 2026-06-16 | Initial bootstrap | halaprix |
| 2026-06-17 | Sync rules with leakwatch standard | halaprix |

Substantive changes to `AGENTS.md` require a PR review by Marian. LLM agents: if you think a rule is wrong, propose a change in an issue; do not silently edit the rulebook.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
