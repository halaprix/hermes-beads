# Dashboard Specification

## Overview

`hb dashboard build` renders a static, read-only project snapshot from Beads issue data. It is an observability surface, not a control plane and not a second source of truth.

## Command

```bash
hb dashboard build --output dashboard.html
hb dashboard build --dry-run --output dashboard.html
```

Dry-run prints the collected public-safe JSON. Apply writes a static HTML file.

## Data collectors

The collector in `src/hermes_beads/dashboard.py` accepts Beads issue dictionaries and optional Hermes Kanban task dictionaries. It intentionally copies only public summary fields:

- bead ID
- title
- status
- priority
- issue type
- assignee/owner
- labels
- selected `hermes_*` metadata
- linked Kanban task ID/status

It does not persist data and does not copy descriptions, comments, raw handoff packets, environment values, or local machine paths.

## Rendered sections

The HTML output has invariant sections rather than a brittle pixel-perfect layout:

- `Summary`
- `Ready Work`
- `All Work`
- `Non-goals`

Tests assert these sections exist and that private-data patterns are rejected.

## Privacy boundaries

The renderer blocks output containing private path, private network, token, or provider-key patterns. Unsafe input values are redacted before rendering when possible, and the final rendered document is scanned again.

Forbidden examples:

- absolute user-machine paths
- private network addresses
- GitHub token prefixes
- provider key environment names
- raw worker transcripts

Allowed examples:

- bead IDs
- public labels
- public task titles
- project-relative file names
- redacted placeholders

## Local serving workflow

The output is just a file, so use any static server:

```bash
hb dashboard build --output dashboard.html
python -m http.server 8000
```

Open the generated file in a browser or serve it from a local-only dashboard host.

## Non-goals

- Editing Beads state
- Approving gates
- Starting workers
- Replacing Hermes Kanban
- Replacing `bd`
- Live WebSocket updates
- Storing historical dashboard snapshots

Future server-side dashboards can reuse the same collector and renderer, but mutation APIs should remain out of scope unless a separate reviewed control-plane design is accepted.
