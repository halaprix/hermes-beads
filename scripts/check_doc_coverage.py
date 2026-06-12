#!/usr/bin/env python3
"""Check Python source docstring coverage for release quality gates."""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"


@dataclass(frozen=True)
class DocItem:
    """A source object that should have a docstring."""

    path: Path
    name: str
    has_docstring: bool


def is_public(name: str) -> bool:
    """Return whether a Python object name is part of the public docs surface."""
    return not name.startswith("_")


def iter_python_files(root: Path) -> list[Path]:
    """Return Python files under root in deterministic order."""
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def collect_doc_items(path: Path) -> list[DocItem]:
    """Collect docstring-bearing public objects from a Python source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    relative = path.relative_to(REPO_ROOT)
    items = [DocItem(relative, "<module>", ast.get_docstring(tree) is not None)]

    class Visitor(ast.NodeVisitor):
        """AST visitor that records public classes and functions."""

        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802 - ast API name
            """Record public classes and continue into their methods."""
            if is_public(node.name):
                items.append(DocItem(relative, node.name, ast.get_docstring(node) is not None))
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802 - ast API name
            """Record public functions and methods."""
            if is_public(node.name):
                items.append(DocItem(relative, node.name, ast.get_docstring(node) is not None))
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802 - ast API name
            """Record public async functions and methods."""
            if is_public(node.name):
                items.append(DocItem(relative, node.name, ast.get_docstring(node) is not None))
            self.generic_visit(node)

    Visitor().visit(tree)
    return items


def calculate_coverage(items: list[DocItem]) -> float:
    """Calculate docstring coverage as a 0.0-1.0 ratio."""
    if not items:
        return 1.0
    documented = sum(item.has_docstring for item in items)
    return documented / len(items)


def main() -> int:
    """Run the doc coverage check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=0.9, help="minimum required doc coverage ratio")
    args = parser.parse_args()

    items: list[DocItem] = []
    for path in iter_python_files(SRC_DIR):
        items.extend(collect_doc_items(path))

    coverage = calculate_coverage(items)
    documented = sum(item.has_docstring for item in items)
    print(f"doc_coverage={coverage:.3f} documented={documented} total={len(items)} threshold={args.threshold:.3f}")

    missing = [item for item in items if not item.has_docstring]
    for item in missing:
        print(f"missing_docstring: {item.path}:{item.name}", file=sys.stderr)

    if coverage < args.threshold:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
