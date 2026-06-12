# Beads Setup Compatibility Matrix

> Defines which Beads (bd) setup modes are supported by hermes-beads (hb),
> which are planned but untested, and which are intentionally unsupported.
> Last updated: 2026-06-12.

## Minimum bd Version

| Requirement | Value |
|-------------|-------|
| Minimum bd version | **1.0.0** |
| Currently installed | 1.0.4 |
| Backend | Dolt (only); legacy SQLite removed in bd 1.0.0 |
| Auto-discovery | bd auto-discovers `.beads/` from cwd; `hb` relies on this |

**2.0 deprecation risk:** bd changelog notes that JSON machine-output shapes
may change in future major versions. `hb` does **not** treat JSON shapes as
unversioned stable API. Tests in `tests/test_compatibility.py` capture stderr
warnings from `bd --json` commands and fail if bd emits deprecation notices
about JSON machine output. Before upgrading to bd 2.x, run the compatibility
test suite and inspect the contract tests.

## Setup Mode Matrix

| Mode | Status | Tested | Notes |
|------|--------|--------|-------|
| Standard embedded Dolt | **Supported** | Yes — automated smoke test | Default `bd init` with embedded Dolt engine. Full hb bridge dispatch/profile dry-run coverage. |
| Stealth embedded Dolt | **Supported** | Yes — automated smoke test | `bd init --stealth` with embedded engine. Per-repo git exclude, no `.beads` tracked. |
| Nested cwd below repo root | **Supported** | Yes — automated smoke test | hb shelling out to `bd` from a subdirectory; bd auto-discovers `.beads/` upward. |
| JSONL-restored repo | **Planned** | No — needs explicit test | `bd init --from-jsonl` may reconstruct a workspace. Not yet verified with hb. Must not rely on `.beads/issues.jsonl` as source of truth. |
| Remote configured (unreachable) | **Provisional** | Partial | Dispatch/profile dry-runs are local-only and should work. Sync/push operations are future ticks — no remote-dependent code exists yet in hb. |
| Server mode | **Unsupported** | No — requires test | `bd init --server` or `--shared-server`. External Dolt SQL server. `hb` has no server-connection pass-through. Needs explicit test before claiming support. |
| Global database | **Unsupported** | No — hb has no pass-through | `bd --global` or `bd --db <path>`. `hb` uses plain `bd` without global/db flags, so only auto-discovered local workspaces work. |
| Read-only / sandbox | **Provisional** | Partial | Read-only dry-runs (`bd --readonly ready --json`) likely work. Apply operations (sync-results --apply) should fail cleanly. Not covered by current smoke tests. |
| `--db` explicit path | **Unsupported** | No — hb has no pass-through | `hb` does not expose `bd --db` to users. Only cwd-based auto-discovery is supported. |

## bd JSON Output Contract

`hb` shells out to `bd ...` and consumes JSON output from four subcommands.
The table below lists the fields `hb` reads from each command.

### `bd ready --json`

```json
[
  {
    "id": "<string>",
    "title": "<string>",
    "description": "<string>",
    "status": "<string>",
    "priority": "<number>",
    "issue_type": "<string>",
    "labels": ["<string>", ...],
    "dependencies": [{ "id": "<string>", "title": "<string>", "status": "<string>" }, ...],
    "metadata": { "hermes_*": "<string>", ... }
  }
]
```

| Field | Type | Consumed by | Notes |
|-------|------|-------------|-------|
| `id` | string | `build_handoff_packet`, `build_kanban_payload` | Primary key |
| `title` | string | `build_handoff_packet` → `goal` | |
| `description` | string | `build_handoff_packet` | |
| `status` | string | (routing, future) | |
| `priority` | number | `build_kanban_payload` | |
| `issue_type` | string | (future) | |
| `labels` | string[] | `explain_profile_selection` | Fallback profile routing |
| `dependencies` | object[] | `_dependency_summary` | Used in handoff packets |
| `metadata` | object | `build_handoff_packet`, `explain_profile_selection` | Read nested `hermes_profile`, `hermes_mode`, `hermes_stop_condition`, `hermes_iteration` |

### `bd show <id> --json`

Returns the same fields as `bd ready --json` for a single bead, plus the
optional `comments` array:

| Field | Type | Consumed by | Notes |
|-------|------|-------------|-------|
| All ready fields | — | Same as `bd ready` | |
| `comments` | object[] | `get_comments` (fallback) | Embedded comments may be absent; hb falls through to `bd comments` |

### `bd comments <id> --json`

```json
[
  {
    "author": "<string>",
    "text": "<string>",
    "created_at": "<datetime>"
  }
]
```

`hb`'s `normalize_comments` reads these flexible keys from each comment object:

| Consumed key | Fallback keys |
|--------------|---------------|
| `author` | `created_by`, `actor` |
| `body` | `text`, `comment`, `content` |
| `created_at` | `timestamp` |

### `bd context --json`

```json
{
  "schema_version": 1,
  ...
}
```

| Field | Type | Consumed by | Notes |
|-------|------|-------------|-------|
| `schema_version` | number | (not yet consumed — contract placeholder) | Marker for future context-aware operations |

## Testing

Automated compatibility tests live in `tests/test_compatibility.py`:

| Test class | Covers |
|------------|--------|
| `TestStandardEmbedded` | Standard Dolt: hb dispatch/profile dry-run |
| `TestStealthEmbedded` | Stealth Dolt: hb dispatch/profile dry-run |
| `TestNestedCwd` | Nested cwd: hb dispatch/profile dry-run |
| `TestJsonStderrClean` | Stderr warning capture for ready/show/comments/context |
| `TestReadyJsonContract` | Contract fields from `bd ready --json` |
| `TestShowJsonContract` | Contract fields from `bd show --json` |
| `TestCommentsJsonContract` | Contract fields from `bd comments --json` |
| `TestContextJsonContract` | Contract fields from `bd context --json` |

## Unsupported Setup Risks

1. **Global/explicit `--db`:** `hb` has no flag pass-through to `bd --db`.
   Users who need non-cwd databases must create an issue or use `bd` directly.
2. **Server mode:** External Dolt SQL server requires server-connection
   configuration that `hb` does not manage. Embedded Dolt is the only tested
   backend.
3. **JSONL as source of truth:** `hb` must never read or write
   `.beads/issues.jsonl` — that file is a passive export only.
4. **JSON shape versioning:** bd 2.x may change JSON output shapes.
   Contract tests will catch missing fields early. Stderr deprecation
   warnings are tested to fail loud on upgrade.
