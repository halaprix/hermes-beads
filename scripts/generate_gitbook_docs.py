#!/usr/bin/env python3
"""Generate GitBook-compatible documentation index files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"

DOC_PAGES = [
    ("Beads Usage", "beads-usage.md"),
    ("Metadata Schema", "metadata-schema.md"),
    ("Handoff Packet", "handoff-packet.md"),
    ("Kanban Bridge", "kanban-bridge.md"),
    ("Product Contract", "product-contract.md"),
    ("Gate Resolver", "gate-resolver.md"),
    ("Beads Compatibility", "beads-compatibility.md"),
    ("Release Matrix", "release-matrix.md"),
    ("Cron Polling", "cron-polling.md"),
    ("Cross-Machine Sync", "cross-machine-sync.md"),
    ("Project Dashboard", "dashboard.md"),
    ("PR Flow", "pr-flow.md"),
    ("Privacy", "privacy.md"),
    ("Roadmap", "roadmap.md"),
]

README = """# Hermes-Beads Documentation

Hermes-Beads connects [Beads](https://github.com/gastownhall/beads) task state with Hermes agent workflows. The project keeps task state durable, public-safe, and reviewable while Hermes agents remain disposable execution workers.

## Start Here

- [Beads Usage](beads-usage.md) — local task graph commands and conventions.
- [Metadata Schema](metadata-schema.md) — public metadata contract used by agents.
- [Handoff Packet](handoff-packet.md) — JSON context shape passed between Beads and Hermes.
- [Kanban Bridge](kanban-bridge.md) — bridge design and implemented dry-run commands.
- [Product Contract](product-contract.md) — authority model, mutation semantics, idempotency rules.
- [Gate Resolver](gate-resolver.md) — profile routing rules.
- [Beads Compatibility](beads-compatibility.md) — supported setup modes, bd output contract, minimum version.

## Project Roadmap

The [Roadmap](roadmap.md) sequences remaining work toward Hermes Agent upstream integration, from the product contract and result-sync idempotency through distribution (TestPyPI → PyPI → upstream skill PR).

## Release Gates

The CI workflow verifies privacy scanning, Python tests, non-editable package install behavior, generated GitBook docs, and code doc coverage above 90%.

See the [Release Matrix](release-matrix.md) for the full pre-PyPI gate checklist, sequencing constraints, and versioning policy.
"""


def render_summary() -> str:
    """Render a GitBook SUMMARY.md table of contents."""
    lines = ["# Summary", "", "* [Overview](README.md)"]
    lines.extend(f"* [{title}]({filename})" for title, filename in DOC_PAGES)
    return "\n".join(lines) + "\n"


def generated_files() -> dict[Path, str]:
    """Return the generated GitBook file contents keyed by destination path."""
    return {
        DOCS_DIR / "README.md": README,
        DOCS_DIR / "SUMMARY.md": render_summary(),
    }


def check_required_pages() -> list[str]:
    """Return missing source documentation pages referenced by GitBook SUMMARY.md.

    Paths with '..' (e.g. '../ROADMAP.md') are intentionally outside DOCS_DIR and
    are checked by resolving to an absolute path — they are not blindly skipped.
    """
    missing = []
    for _title, filename in DOC_PAGES:
        path = (DOCS_DIR / filename).resolve()
        if not path.exists():
            missing.append(filename)
    return missing


def write_files(files: dict[Path, str]) -> None:
    """Write generated files to disk."""
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")


def check_files(files: dict[Path, str]) -> list[str]:
    """Return paths whose generated content is missing or stale."""
    stale = []
    for path, expected in files.items():
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            stale.append(str(path.relative_to(REPO_ROOT)))
    return stale


def main() -> int:
    """Run the GitBook docs generator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if generated docs are stale")
    args = parser.parse_args()

    missing = check_required_pages()
    if missing:
        print("Missing docs pages: " + ", ".join(missing), file=sys.stderr)
        return 1

    files = generated_files()
    if args.check:
        stale = check_files(files)
        if stale:
            print("GitBook docs are stale; run scripts/generate_gitbook_docs.py", file=sys.stderr)
            for path in stale:
                print(f"- {path}", file=sys.stderr)
            return 1
        print("GitBook docs are current")
        return 0

    write_files(files)
    print("Generated GitBook docs: docs/README.md, docs/SUMMARY.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
