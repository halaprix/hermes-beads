# hermes-beads

Bridge [Beads](https://github.com/gastownhall/beads) task state into Hermes Agent workflows.

`hermes-beads` provides the `hb` CLI. It treats Beads as the durable task graph and Hermes workers as disposable execution agents:

- `bd` tracks **what** needs doing in a local Dolt-backed issue database
- Hermes profiles decide **who** should do the work
- `hb bridge ...` previews and syncs the handoff between the two

## Install

```bash
pip install hermes-beads
```

You also need the Beads CLI (`bd`) in projects where you want to manage task state:

```bash
curl -fsSL https://raw.githubusercontent.com/gastownhall/beads/main/scripts/install.sh | bash
bd version
```

## Quick start

```bash
# in a project repository
bd init --prefix demo --quiet
bd prime

# inspect bridge behavior without side effects
hb --version
hb bridge dispatch --dry-run
```

## Commands

```bash
hb --version
hb bridge dispatch --dry-run
hb bridge profile <bead-id> --dry-run
hb bridge sync-results --dry-run --results-file results.json
hb bridge sync-results --apply --results-file results.json
```

## Release gates

The repository CI and local release checks cover:

- privacy scan (`scripts/scan-privacy.sh`)
- pytest suite
- generated GitBook docs check
- docstring coverage gate above 90%
- non-editable install smoke test (`pip install . && hb --version`)

## Documentation

Full docs live in [`docs/`](docs/README.md).

## License

MIT. See [`LICENSE`](LICENSE).
