# Local-File Temp-Product Smoke

This is the recommended end-to-end sanity check for hermes-beads before shipping changes that affect dispatch or result sync.

The loop exercises a fresh Beads workspace, local-file dispatch apply, fake worker results, and result sync.

## Prerequisites

- `bd` is on `PATH`
- `hb` is available either from the source tree (`python -m hermes_beads.cli`) or as an installed console script
- `git` is available

## Source-tree smoke

```bash
# from the hermes-beads repo
python -m pytest tests/test_integration_smoke.py -q
```

## Manual temp-product loop

```bash
mkdir -p /tmp/hb-smoke && cd /tmp/hb-smoke
git init -q
bd init --prefix smoke --quiet --non-interactive --skip-agents --skip-hooks

bd create "Local-file smoke" \
  --type task \
  --priority 1 \
  --metadata '{"hermes_profile":"ts-dev","hermes_mode":"pr","hermes_status":"ready"}' \
  --json

hb bridge dispatch --apply --backend local-file --queue-file .queue/dispatch.json
```

Write a fake result file using the task ID from `.queue/dispatch.json`:

```bash
cat > results.json <<'JSON'
[
  {
    "source_bead_id": "<bead-id-from-bd-create>",
    "dispatch_id": "<task-id-from-queue>",
    "status": "completed",
    "summary": "smoke completed"
  }
]
JSON

hb bridge sync-results --apply --results-file results.json
```

Verify the bead is closed and the comment was written:

```bash
bd show <bead-id> --json
bd comments <bead-id> --json
```

## Installed wheel smoke

Build and install the wheel in a clean venv, then run the same loop with the installed `hb` binary:

```bash
python -m build
python -m venv /tmp/hb-smoke-venv
/tmp/hb-smoke-venv/bin/pip install dist/hermes_beads-*.whl
/tmp/hb-smoke-venv/bin/hb bridge dispatch --apply --backend local-file --queue-file .queue/dispatch.json
/tmp/hb-smoke-venv/bin/hb bridge sync-results --apply --results-file results.json
```

## Repeat check

Run the same dispatch and sync commands again. A healthy local-file workflow should not create duplicate queue entries or duplicate result comments.
