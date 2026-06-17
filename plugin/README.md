# hermes-beads Dashboard Plugin

Hermes Agent dashboard plugin that renders a visual Beads task graph (DAG) with
clickable nodes for inspecting and dispatching beads.

## Installation

```bash
# Symlink the plugin into Hermes plugins directory
ln -s $(pwd)/plugin ~/.hermes/plugins/hermes-beads

# Or copy it
cp -r plugin ~/.hermes/plugins/hermes-beads

# Restart the dashboard
hermes dashboard --stop
hermes dashboard --host 0.0.0.0 --insecure --no-open
```

## Structure

```
plugin/dashboard/
├── manifest.json      # Tab registration + metadata
├── plugin_api.py      # FastAPI backend routes
└── dist/
    └── index.js       # Frontend entry (placeholder → vis-network DAG in Phase 3)
```

## API Endpoints

All under `/api/plugins/hermes-beads/`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/hello` | Health check |
| GET | `/beads` | All beads in workspace |
| GET | `/beads/ready` | Unblocked beads only |
| GET | `/beads/{id}` | Single bead detail |
| GET | `/beads/graph` | DAG data (nodes + edges) |

## Development

The plugin uses `bd --json` under the hood. It walks up from CWD to find
a `.beads/` directory. Works with any Beads workspace.

Phase roadmap:
- **dv1** (this): Scaffold — route registration, basic API, placeholder UI ✓
- **dv2**: Data layer — JSONL reader, Pydantic models, in-memory store
- **dv3**: Graph visualization — vis-network DAG, neon glow nodes, edge mapping
- **dv4**: Interactions — click to dispatch, gating, completion animations
- **dv5**: Migration — deprecate old CLI, redirect to dashboard
