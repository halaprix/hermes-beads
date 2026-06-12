"""Shared pytest fixtures for hermes-beads tests."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the hermes-beads wheel once per test module, reused across tests."""
    tmp_dir = tmp_path_factory.mktemp("wheel_build")
    repo_root = Path(__file__).resolve().parents[1]
    dist_dir = tmp_dir / "dist"
    dist_dir.mkdir()

    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir), str(repo_root)],
        check=True,
        capture_output=True,
        text=True,
    )

    wheels = list(dist_dir.glob("*.whl"))
    assert len(wheels) == 1, f"Expected exactly one wheel, got {wheels}"
    return wheels[0]
