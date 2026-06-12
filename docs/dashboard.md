# Dashboard Specification

## Overview

The future hermes-beads dashboard should show the live relationship between durable Beads project state and Hermes execution state. It is an observability surface, not a second source of truth.

## Goals

- Show ready, running, blocked, failed, and closed beads
- Show which Hermes profile is working on each bead
- Show bridge lag between Beads and Hermes Kanban
- Show failed tasks and retry counts
- Expose a debug view with raw public-safe packet data

## Views

### Project State

- Count of open, ready, blocked, and closed beads
- Dependency graph summary
- Recently updated beads
- Ready queue ordered by priority

### Agent Health

- Active Hermes workers
- Current bead per worker
- Last heartbeat or update time
- Failure/retry count

### Bridge Health

- Last dispatch run
- Last result-sync run
- Number of pending dispatch operations
- Number of pending result-sync operations

### Debug View

The debug view can show:

- Handoff packet JSON
- Kanban payload JSON
- Planned result-sync operations
- Bead metadata

The debug view must not show secrets, private IPs, local paths, or machine identifiers.

## Data Sources

- `bd ready --json`
- `bd list --json` when available
- `bd show <id> --json`
- Hermes Kanban task list/show commands
- Bridge dry-run commands from `hb bridge dispatch --dry-run` and `hb bridge sync-results --dry-run`

## Privacy Boundaries

The dashboard is allowed to display public project state only. It must not display:

- Tokens or environment variables
- Local filesystem paths
- Private hostnames
- Private network addresses
- Full internal agent transcripts

## Non-Goals

- Editing Beads state from the dashboard
- Replacing Beads CLI
- Replacing Hermes Kanban
- Real-time WebSocket implementation in the first version

## First Version

The first implementation should be a read-only static or server-rendered page that refreshes on demand. The dashboard can be served alongside Hermes later, but the initial version should stay decoupled and easy to run locally.
