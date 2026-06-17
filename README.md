# hermes-beads

🐝 Visual task graph for [Beads](https://github.com/gastownhall/beads) issues — rendered as an interactive DAG inside the [Hermes Agent](https://github.com/NousResearch/hermes-agent) dashboard.

> **v2.0.0-beta.1** — Standalone `hb` CLI is deprecated in favour of the dashboard plugin.
> The `hermes_beads` Python package remains (it powers the plugin's data layer), but
> `pip install hermes-beads` is no longer the primary install path.

## Install (Dashboard Plugin)

```bash
# Symlink into Hermes plugins
ln -s $(pwd)/plugin ~/.hermes/plugins/hermes-beads

# Restart the dashboard
hermes dashboard --stop
hermes dashboard --host 0.0.0.0 --insecure --no-open
```

The "Beads" tab appears in the dashboard sidebar. Navigate to it to see your
bead dependency graph with neon glow styling, clickable nodes, dispatch
buttons, status filters, and 30s auto-refresh.

## Legacy CLI

The standalone `hb` CLI still works but is no longer the primary interface:

```bash
pip install -e .
hb --version
hb bridge dispatch --dry-run
```

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
