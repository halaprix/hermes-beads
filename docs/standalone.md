# Standalone viewer plan

`hermes-beads` should remain useful for Beads users who do not run Hermes Agent.
The standalone path should reuse the existing data layer and graph UI instead of
forking the product.

## Goal

Provide an `hb serve` command that starts a local web UI for any Beads workspace:

```bash
pip install hermes-beads
hb serve --project . --host localhost --port 8765
```

The browser opens a local page that shows the same bead DAG, status filters,
search, and detail panel as the Hermes dashboard plugin.

## Non-goals

- No Hermes Agent dependency.
- No dispatcher or profile execution in the first standalone release.
- No remote hosting by default; bind to localhost unless the user explicitly
  chooses otherwise.
- No separate frontend implementation.

## Architecture

| Layer | Hermes plugin | Standalone viewer |
| --- | --- | --- |
| Data model | `hermes_beads.bead_model` | same |
| Project discovery | `hermes_beads.bead_reader` | same |
| Graph builder | `hermes_beads.graph_builder` | same |
| HTTP API | `plugin/dashboard/plugin_api.py` | shared router or thin adapter |
| Frontend | `plugin/dashboard/dist/index.js` | same bundle, standalone SDK shim |
| Entry point | Hermes dashboard | `hb serve` |

## Implementation sketch

1. Extract backend route registration into reusable functions so the plugin and
   standalone server mount the same API surface.
2. Add a tiny SDK shim for standalone mode:
   - `React` and hooks from bundled frontend dependencies or CDN/vendor assets.
   - `fetchJSON(path, opts)` wrapping browser `fetch`.
   - Minimal component shims for `Card`, `Button`, `Badge`, `Input`, `Select`.
3. Add `hb serve`:
   - Starts a local Python web app with the shared API routes.
   - Serves `plugin/dashboard/dist/index.js` and the standalone HTML shell.
   - Defaults to `localhost:8765`.
4. Add smoke tests:
   - `hb serve --help` works after non-editable install.
   - API returns projects/graph from a fixture Beads workspace.
   - Static shell contains the plugin bundle and SDK shim.

## Release shape

Ship as a minor/beta feature behind explicit CLI invocation:

```bash
hb serve
```

Hermes users keep installing the dashboard plugin. Non-Hermes users install the
Python package and run the local viewer.
