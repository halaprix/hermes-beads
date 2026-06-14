# Release Publishing

This document defines the TestPyPI → PyPI → Hermes Agent upstream path.

## Trusted Publishing workflow

The repository includes `.github/workflows/publish.yml`.

Required GitHub environments:

- `testpypi` with Trusted Publishing configured for the TestPyPI project
- `pypi` with Trusted Publishing configured for the PyPI project

No long-lived package index token is required when Trusted Publishing is configured. If a maintainer chooses token auth instead, store tokens as environment-scoped secrets and do not commit them.

## TestPyPI first

A version must ship to TestPyPI before real PyPI.

```bash
git tag -s v1.1.0a1 -m "v1.1.0a1"
git push origin v1.1.0a1
```

The tag triggers the publish workflow against TestPyPI. Verification requires a clean environment install:

```bash
python -m venv /tmp/hb-testpypi-smoke
/tmp/hb-testpypi-smoke/bin/pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ hermes-beads==1.1.0a1
/tmp/hb-testpypi-smoke/bin/hb --version
```

Then run a small temp-product smoke:

```bash
mkdir /tmp/hb-product-smoke && cd /tmp/hb-product-smoke
git init -q
bd init --prefix smoke --quiet --non-interactive --skip-agents --skip-hooks
hb bridge dispatch --dry-run
```

## Real PyPI

Only after TestPyPI install and smoke pass, trigger the workflow manually with `repository=pypi`.

```bash
# GitHub UI: Actions → Publish Python package → Run workflow → repository=pypi
```

Verify real PyPI from a clean environment:

```bash
python -m venv /tmp/hb-pypi-smoke
/tmp/hb-pypi-smoke/bin/pip install hermes-beads==1.1.0a1
/tmp/hb-pypi-smoke/bin/hb --version
```

## Rollback and version bump policy

PyPI artifacts are immutable. Do not delete or replace a bad public release as a normal recovery path. Fix forward:

1. leave the bad artifact in place
2. document the issue in `CHANGELOG.md`
3. bump the version
4. publish a new tag and package

For TestPyPI-only failures, reuse is still discouraged. Prefer a new alpha version such as `1.1.0a2` so smoke logs and package metadata remain unambiguous.

## Upstream Hermes skill preparation

After real PyPI works, prepare the Hermes Agent skill in this repo first under `skills/hermes-beads/`. Open the upstream PR only after explicit maintainer instruction.
