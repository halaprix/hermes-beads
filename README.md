# hermes-beads

🐝 Visual task graph for [Beads](https://github.com/gastownhall/beads) issues — rendered as an interactive DAG inside the [Hermes Agent](https://github.com/NousResearch/hermes-agent) dashboard.

> **v2.0.0-beta.1** — Standalone `hb` CLI is deprecated in favour of the dashboard plugin.
> The `hermes_beads` Python package remains (it powers the plugin's data layer), but
> `pip install hermes-beads` is no longer the primary install path.

## Install (Dashboard Plugin)

```bash
# Symlink into Hermes plugins
ln -s $(pwd)/plugin ~/.hermes/plugins/hermes-beads

# Enable the user plugin. Hermes dashboard user plugins are opt-in.
hermes plugins enable hermes-beads

# Restart the dashboard so backend routes are mounted
hermes dashboard --stop
hermes dashboard --host 0.0.0.0 --insecure --no-open
```

The "Beads" tab appears in the dashboard sidebar. Navigate to it to see your
bead dependency graph with neon glow styling, clickable nodes, dispatch
buttons, status filters, and 30s auto-refresh.

If you installed an older checkout before `plugin/plugin.yaml` existed and the
tab does not appear, either re-sync the plugin directory and run the enable
command above, or add `hermes-beads` to `plugins.enabled` in
`~/.hermes/config.yaml` and restart the dashboard.

## Standalone / non-Hermes use

The `hb` CLI remains available for users who do not run Hermes:

```bash
pip install -e .
hb --version
hb bridge dispatch --dry-run
```

The visual DAG currently ships as a Hermes dashboard plugin. A standalone web
viewer should reuse the same `hermes_beads` data layer and `plugin/dashboard`
frontend bundle, but serve it from an `hb serve` command instead of the Hermes
dashboard. See [`docs/standalone.md`](docs/standalone.md) for the proposed
shape.

## API

All endpoints under `/api/plugins/hermes-beads/api/`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects` | Discover all Beads projects |
| GET | `/projects/<name>/beads` | List beads for a project |
| GET | `/projects/<name>/graph` | DAG data for vis-network |
| POST | `/projects/<name>/dispatch` | Dispatch selected beads |
| POST | `/projects/<name>/gate/<id>` | Resolve blocking gate |

## License

MIT. See [`LICENSE`](LICENSE).
