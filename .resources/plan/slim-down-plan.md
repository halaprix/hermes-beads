# hermes-beads Slim-Down Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip cargo-cult packaging/GitBook/release ceremony from `hermes-beads` while keeping the real bridge (bd → Hermes Kanban dispatch + result-sync idempotency). Reduce ~55% of non-test content. One commit per change. Push after each commit.

**Architecture:** Cut in three phases, each a single self-contained commit:
1. **Phase 1 — Dead code:** Remove modules that are stubs or unused (gates, dashboard, bd_helpers inline, orphan skill, VERSION file, gates/dashboard tests).
2. **Phase 2 — Publication ceremony:** Drop GitBook docs, doc-coverage script, publish workflow, packaging/quality-gate tests, prune dead `hb` subcommands.
3. **Phase 3 — Surface shrink:** Slim `pyproject.toml` classifiers, drop `--dry-run`-only stubs, consolidate into single source of truth.

Each phase = 1 commit, 1 push, 1 bead closed. Beads are created from this plan and executed sequentially.

**Tech Stack:** Python 3.11+, Click, Beads (bd), pytest. No new deps.

**Repo:** `/home/pkl/workspace/hermes-beads` (branch: `main`, remote: `halaprix/hermes-beads`).

**Execution environment:** local dev box (pkl, `/home/pkl`). All commands run from `/home/pkl/workspace/hermes-beads`. No SSH, no remote workers.

**Pre-flight gates** (run before each commit):
```bash
cd /home/pkl/workspace/hermes-beads
pytest -x -q                  # 30+ tests must pass
python -c "from hermes_beads import cli; cli.main(['--version'])"  # CLI must boot
```

---

## File Structure

**Files to DELETE (Phase 1 — dead code):**
- `src/hermes_beads/gates.py` (103 lines, dry-run-only stub per roadmap)
- `src/hermes_beads/dashboard.py` (170 lines, static HTML for 1 user)
- `tests/test_gates.py` (63 lines, follows gates.py)
- `tests/test_dashboard.py` (52 lines, follows dashboard.py)
- `skills/hermes-beads/SKILL.md` (orphan; upstream PR hasn't happened)
- `VERSION` (replace with importlib.metadata from pyproject.toml)
- `tests/test_bd_helpers.py` (inlined — 176 lines obsolete after step 1.3)

**Files to DELETE (Phase 2 — publication ceremony):**
- `docs/` (all 21 .md files, ~50KB) — GitBook nobody reads
- `scripts/generate_gitbook_docs.py` — generates the above
- `scripts/check_doc_coverage.py` — 90% docstring gate
- `.github/workflows/publish.yml` — never run, externally blocked
- `tests/test_packaging.py` — gate test for ceremony being removed
- `tests/test_quality_gates.py` — gate test for ceremony being removed
- `tests/test_privacy_scan.py` — depends on `scan-privacy.sh` paths being canonical; keep scan-privacy.sh but drop this gate (manual only)

**Files to MODIFY:**
- `src/hermes_beads/cli.py` — inline bd_helpers (Phase 1), drop `gates`/`dashboard`/`hb gates`/`hb dashboard` subcommands, drop dry-run-only stubs (Phase 2/3)
- `src/hermes_beads/__init__.py` — drop `__version__` VERSION-file read; use importlib.metadata
- `pyproject.toml` — slim classifiers, drop keywords, drop dev extras, drop `[project.urls]` (Phase 3)
- `.github/workflows/ci.yml` — remove gitbook-docs job and doc-coverage step (Phase 2)

**Files to KEEP (the real bridge):**
- `src/hermes_beads/cli.py` (slimmed, ~500 lines)
- `src/hermes_beads/dispatch_ops.py` (280 lines)
- `src/hermes_beads/result_ops.py` (77 lines)
- `src/hermes_beads/tick_ops.py` (158 lines)
- `src/hermes_beads/hermes_kanban_backend.py` (149 lines)
- `src/hermes_beads/local_file_backend.py` (111 lines)
- `src/hermes_beads/__init__.py` (1 line, but rewritten)
- `tests/test_cli.py` (923 lines)
- `tests/test_dispatch_ops.py` (368 lines)
- `tests/test_hermes_kanban_backend.py` (169 lines)
- `tests/test_local_file_backend.py` (107 lines)
- `tests/test_result_ops.py` (109 lines)
- `tests/test_tick_ops.py` (80 lines)
- `tests/test_integration_smoke.py` (298 lines)
- `tests/test_compatibility.py` (526 lines)
- `tests/conftest.py` (28 lines)
- `scripts/scan-privacy.sh` (manual utility, not a gate)
- `README.md` (rewrite to reflect new surface in Phase 3)
- `CHANGELOG.md` (rewrite — drop SemVer pantomime note)
- `AGENTS.md` (untouched)
- `CLAUDE.md`, `CONTRIBUTING.md`, `LICENSE`, `SECURITY.md` (kept but slimmed in Phase 3)
- `Makefile` (2 lines — kept as-is, harmless)

---

## Task 1: Phase 1 — Remove dead code

**Files:**
- Delete: `src/hermes_beads/gates.py`, `src/hermes_beads/dashboard.py`, `tests/test_gates.py`, `tests/test_dashboard.py`, `skills/hermes-beads/SKILL.md`, `tests/test_bd_helpers.py`
- Modify: `src/hermes_beads/cli.py` (drop `gates`/`dashboard` subcommands, inline bd_helpers)
- Modify: `src/hermes_beads/__init__.py` (drop VERSION-file read)
- Delete: `VERSION`

- [ ] **Step 1.1: Read cli.py to map gates/dashboard/bd_helpers usage**

Read `src/hermes_beads/cli.py` end-to-end. List every import from `gates`, `dashboard`, `bd_helpers`. List every `@cli.command()` registered. Note `__version__` reference.

- [ ] **Step 1.2: Delete dead source modules**

```bash
cd /home/pkl/workspace/hermes-beads
git rm src/hermes_beads/gates.py src/hermes_beads/dashboard.py
git rm tests/test_gates.py tests/test_dashboard.py
git rm -r skills/        # entire orphan dir
git rm VERSION
```

- [ ] **Step 1.3: Inline bd_helpers.py into cli.py**

The 100 lines in `bd_helpers.py` are just `subprocess.run` wrappers that convert `CalledProcessError` → `ClickException`. Inline them at the top of `cli.py` as private functions. Then delete the module:

```bash
git rm src/hermes_beads/bd_helpers.py
git rm tests/test_bd_helpers.py
```

Verify imports still resolve: `python -c "from hermes_beads import cli"`.

- [ ] **Step 1.4: Drop gates/dashboard subcommands from cli.py**

In `cli.py`, remove every `@cli.command()` that registers `gates` or `dashboard`. Also remove their `import` lines and any helper functions used only by those commands.

- [ ] **Step 1.5: Replace VERSION-file __version__ with importlib.metadata**

In `src/hermes_beads/__init__.py`:

```python
from importlib.metadata import version as _v, PackageNotFoundError
try:
    __version__ = _v("hermes-beads")
except PackageNotFoundError:
    __version__ = "0.0.0+local"
```

(1 line, replaces the 1-line file read.)

- [ ] **Step 1.6: Run gates**

```bash
cd /home/pkl/workspace/hermes-beads
pytest -x -q
```

Expected: all remaining tests pass (gates/dashboard tests are gone, so 0 failures from them). If any test in kept files references deleted symbols, fix it.

- [ ] **Step 1.7: Commit and push**

```bash
cd /home/pkl/workspace/hermes-beads
git add -A
git status   # verify only the expected deletions + the cli.py/__init__.py edits
git commit -m "refactor: remove dead gates/dashboard/bd_helpers modules

- Drop src/hermes_beads/gates.py (dry-run-only stub, roadmap admits)
- Drop src/hermes_beads/dashboard.py (static HTML for one user)
- Inline bd_helpers.py into cli.py (3 thin subprocess wrappers)
- Delete orphan skills/hermes-beads/ (no upstream PR)
- Replace VERSION file with importlib.metadata in __init__.py
- Drop tests for removed modules

Bead: hermes-beads-XXX (Phase 1)"
git push
```

- [ ] **Step 1.8: Close Phase 1 bead**

```bash
cd /home/pkl/workspace/hermes-beads
bd close hermes-beads-XXX --reason "Phase 1 dead code removed, all tests pass, pushed"
bd dolt push
```

---

## Task 2: Phase 2 — Remove publication ceremony

**Files:**
- Delete: `docs/` (21 files), `scripts/generate_gitbook_docs.py`, `scripts/check_doc_coverage.py`, `.github/workflows/publish.yml`, `tests/test_packaging.py`, `tests/test_quality_gates.py`, `tests/test_privacy_scan.py`
- Modify: `src/hermes_beads/cli.py` (drop `hb bridge profile --dry-run` if it's a forced dry-run stub; verify before deleting)
- Modify: `.github/workflows/ci.yml` (remove gitbook-docs job and doc-coverage step)
- Keep: `scripts/scan-privacy.sh` (manual utility, not a CI gate)

- [ ] **Step 2.1: Verify hb bridge profile is forced-dry-run**

```bash
cd /home/pkl/workspace/hermes-beads
grep -n "bridge profile" src/hermes_beads/cli.py | head -20
```

Read the implementation. If the only non-dry-run code path is a `sys.exit(1)` when `--dry-run` is missing (i.e. it's a printout, not a command), delete it. Otherwise keep it.

- [ ] **Step 2.2: Delete docs/ directory and GitBook scripts**

```bash
cd /home/pkl/workspace/hermes-beads
git rm -r docs/
git rm scripts/generate_gitbook_docs.py scripts/check_doc_coverage.py
```

The `scan-privacy.sh` script stays — it's useful as a manual command, not a CI gate.

- [ ] **Step 2.3: Delete packaging/quality-gate tests**

```bash
cd /home/pkl/workspace/hermes-beads
git rm tests/test_packaging.py tests/test_quality_gates.py tests/test_privacy_scan.py
```

- [ ] **Step 2.4: Delete publish workflow**

```bash
cd /home/pkl/workspace/hermes-beads
git rm .github/workflows/publish.yml
```

- [ ] **Step 2.5: Slim ci.yml**

In `.github/workflows/ci.yml`:
- Remove the `gitbook-docs` job (entire block)
- Remove the `doc-coverage` step from the main test job
- Keep: `pytest` step

Read the file first, then patch.

- [ ] **Step 2.6: Drop dry-run-only hb subcommand (if verified in 2.1)**

If `hb bridge profile` is a forced-dry-run stub, remove its `@cli.command()` and any helper from `cli.py`.

- [ ] **Step 2.7: Run gates**

```bash
cd /home/pkl/workspace/hermes-beads
pytest -x -q
python -c "from hermes_beads import cli; cli.main(['--version'])"
```

Expected: tests pass, CLI boots, `--version` prints the importlib.metadata value.

- [ ] **Step 2.8: Update README to reflect new surface**

In `README.md`:
- Remove `hb dashboard build` from the Commands list
- Remove `hb gates list` / `hb gates approve` from the Commands list
- Remove references to `docs/`, GitBook, PyPI publish
- Update Quick start to not mention `hb bridge profile`
- Update "Release gates" section to be empty/removed

- [ ] **Step 2.9: Commit and push**

```bash
cd /home/pkl/workspace/hermes-beads
git add -A
git status
git commit -m "refactor: drop GitBook docs and PyPI publication ceremony

- Remove docs/ (21 GitBook files, ~50KB) — generated for a site that doesn't exist
- Remove scripts/generate_gitbook_docs.py and check_doc_coverage.py (90% gate)
- Remove .github/workflows/publish.yml (Trusted Publishing, never run, externally blocked)
- Remove test_packaging.py, test_quality_gates.py, test_privacy_scan.py (gate tests for ceremony)
- Slim ci.yml to pytest only
- Update README to reflect new surface

Bead: hermes-beads-YYY (Phase 2)"
git push
```

- [ ] **Step 2.10: Close Phase 2 bead**

```bash
cd /home/pkl/workspace/hermes-beads
bd close hermes-beads-YYY --reason "Phase 2 publication ceremony removed, tests pass, pushed"
bd dolt push
```

---

## Task 3: Phase 3 — Surface shrink and final cleanup

**Files:**
- Modify: `pyproject.toml` (slim classifiers, drop keywords, drop dev extras, drop `[project.urls]`)
- Modify: `src/hermes_beads/cli.py` (final pass — any remaining dead helpers)
- Modify: `CHANGELOG.md` (rewrite — drop SemVer pantomime entry, document this refactor as the new baseline)
- Modify: `SECURITY.md` (slim if oversized), `CONTRIBUTING.md` (slim if oversized)
- Verify: `Makefile`, `AGENTS.md`, `CLAUDE.md` — keep as-is unless they reference removed features

- [ ] **Step 3.1: Slim pyproject.toml**

Read `pyproject.toml`, then:
- Reduce `[project]` classifiers from 9 to 2 (`"Programming Language :: Python :: 3"`, `"Operating System :: POSIX :: Linux"`)
- Drop `keywords = [...]`
- Drop `dev` extras (or keep one minimal `[test]` extra with `pytest` only)
- Drop `[project.urls]` (Homepage, Repository, Issues) — single user, no public surface
- Keep: `[project]`, `[project.scripts] hb = ...`, `[build-system]`

- [ ] **Step 3.2: Final dead-code pass in cli.py**

```bash
cd /home/pkl/workspace/hermes-beads
grep -nE "def [a-z_]+\(" src/hermes_beads/cli.py | head -50
```

For each function, verify it's called by a `@cli.command()` or by another called function. If orphan, delete.

- [ ] **Step 3.3: Rewrite CHANGELOG.md**

Drop entries for 0.1.0, 0.2.0, 0.3.0, 1.0.0, 1.1.0a1 (SemVer pantomime with no consumers). Add a single new entry at the top:

```markdown
## [Unreleased]

### Changed
- **Refactor:** stripped cargo-cult packaging ceremony. Removed GitBook docs, PyPI publish workflow, docstring coverage gate, dry-run-only `gates` and `dashboard` modules, and unused helpers. Bridge surface (bd ↔ Hermes Kanban dispatch, result-sync idempotency, tick/cron) is unchanged. See `docs/superpowers/plans/2026-06-15-hermes-beads-slim-down.md` (now in `~/.hermes/plans/`) for the rationale.
```

- [ ] **Step 3.4: Slim CONTRIBUTING.md and SECURITY.md if oversized**

Read both. If either has sections referencing removed features (publishing flow, GitBook, gates, dashboard), delete those sections. Otherwise leave.

- [ ] **Step 3.5: Run final gates**

```bash
cd /home/pkl/workspace/hermes-beads
pytest -x -q
python -c "from hermes_beads import cli; print(cli.main(['--version']))"
python -c "import hermes_beads; print(hermes_beads.__version__)"
pip install -e . --quiet && hb --version
```

Expected: all green.

- [ ] **Step 3.6: Repo size sanity check**

```bash
cd /home/pkl/workspace/hermes-beads
echo "=== src/ ==="
wc -l src/hermes_beads/*.py
echo "=== tests/ ==="
wc -l tests/*.py
echo "=== root files ==="
ls -la *.md *.toml VERSION Makefile 2>&1 | head -20
```

Expected: src/ ~1,300 lines (down from 1,836), tests/ ~2,500 lines (down from 3,033), no `docs/` dir, no `VERSION` file, no `skills/` dir, no `publish.yml`.

- [ ] **Step 3.7: Commit and push**

```bash
cd /home/pkl/workspace/hermes-beads
git add -A
git status
git commit -m "refactor: slim pyproject surface and finalize slim-down

- Slim pyproject.toml classifiers from 9 to 2, drop keywords/urls/dev extras
- Final dead-code pass on cli.py
- Rewrite CHANGELOG.md to drop SemVer pantomime (0.1.0→1.1.0a1 in 3 days with no consumers)
- Slim CONTRIBUTING.md and SECURITY.md if they referenced removed features

Bead: hermes-beads-ZZZ (Phase 3)"
git push
```

- [ ] **Step 3.8: Close Phase 3 bead + verify final state**

```bash
cd /home/pkl/workspace/hermes-beads
bd close hermes-beads-ZZZ --reason "Phase 3 surface shrink complete, all gates green, pushed"
bd dolt push
bd list --status closed | head -5  # verify 3 new closed beads
```

---

## Self-Review

**Spec coverage:**
- Three review consensus (agy + codex + claude) ✓ — all items mapped to a task
- One commit per change ✓ — Task 1.7, 2.9, 3.7 each commit exactly one phase
- Push after each commit ✓ — `git push` in every commit step
- Beads created and closed per phase ✓ — Steps 1.8, 2.10, 3.8
- All pytest gates pass ✓ — Steps 1.6, 2.7, 3.5

**Placeholder scan:** No "TBD" / "TODO" / "implement later". All commands are complete.

**Type consistency:** Function names (`gates`, `dashboard`, `bd_helpers`) match the imports in cli.py and the test files. Removal of test files matches removal of source files in the same task.

**Bead creation order:** Create beads BEFORE starting Task 1. The plan assumes `hermes-beads-XXX`, `hermes-beads-YYY`, `hermes-beads-ZZZ` exist with status `open`. Replace `XXX/YYY/ZZZ` with the real IDs after `bd create`.

---

## Pre-Plan Step: Create the three beads

Before starting Task 1, run:

```bash
cd /home/pkl/workspace/hermes-beads

bd create --title "Phase 1: Remove dead code (gates/dashboard/bd_helpers)" \
  --description "Drop gates.py, dashboard.py, inline bd_helpers.py, delete orphan skills/, drop VERSION file, drop tests for removed modules. One commit. Bead closes when push succeeds and pytest passes." \
  --type task --priority high

bd create --title "Phase 2: Remove publication ceremony (GitBook/PyPI)" \
  --description "Drop docs/, generate_gitbook_docs.py, check_doc_coverage.py, publish.yml, packaging/quality-gate tests. Slim ci.yml to pytest only. Update README. One commit. Bead closes when push succeeds and pytest passes." \
  --type task --priority high

bd create --title "Phase 3: Slim pyproject surface and finalize" \
  --description "Slim pyproject.toml classifiers/keywords/urls. Final dead-code pass on cli.py. Rewrite CHANGELOG.md to drop SemVer pantomime. Slim CONTRIBUTING/SECURITY if needed. One commit. Bead closes when push succeeds and pytest passes." \
  --type task --priority medium

bd ready  # verify all three are listed
```

Note the real bead IDs and substitute them for `XXX/YYY/ZZZ` in the tasks above.
