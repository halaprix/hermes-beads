"""Repository quality gate tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_repo_script(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a repository script with the current Python interpreter."""
    repo_root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, str(repo_root / "scripts" / script), *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )


def test_gitbook_docs_are_generated_and_current() -> None:
    """Generated GitBook docs must be reproducible from tracked sources."""
    result = run_repo_script("generate_gitbook_docs.py", "--check")
    assert result.returncode == 0, result.stderr + result.stdout


def test_code_doc_coverage_exceeds_release_threshold() -> None:
    """Public source objects must keep docstring coverage above 90%."""
    result = run_repo_script("check_doc_coverage.py", "--threshold", "0.9")
    assert result.returncode == 0, result.stderr + result.stdout
