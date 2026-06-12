"""Packaging regression tests for release artifacts."""

from __future__ import annotations

import subprocess
import sys
from shutil import copytree, ignore_patterns
from pathlib import Path


def test_non_editable_install_exposes_working_cli(tmp_path: Path) -> None:
    """A normal installed package must expose a working hb console script."""
    repo_root = Path(__file__).resolve().parents[1]
    source_dir = tmp_path / "source"
    venv_dir = tmp_path / "venv"

    copytree(
        repo_root,
        source_dir,
        ignore=ignore_patterns(".git", ".pytest_cache", "__pycache__", "*.pyc"),
    )
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    subprocess.run(
        [str(venv_dir / "bin" / "python"), "-m", "pip", "install", "-q", str(source_dir)],
        check=True,
    )

    result = subprocess.run(
        [str(venv_dir / "bin" / "hb"), "--version"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    expected_version = (repo_root / "VERSION").read_text().strip()
    assert f"hb, version {expected_version}" in result.stdout


class TestInstalledWheel:
    """Installed package via built wheel (not editable/source install)."""

    def test_hb_version_from_installed_wheel(self, tmp_path: Path, built_wheel: Path) -> None:
        """Build a wheel, pip install it in a temp venv, verify hb works."""
        repo_root = Path(__file__).resolve().parents[1]
        venv_dir = tmp_path / "venv"

        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        subprocess.run(
            [str(venv_dir / "bin" / "python"), "-m", "pip", "install", "-q", str(built_wheel)],
            check=True,
        )

        result = subprocess.run(
            [str(venv_dir / "bin" / "hb"), "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        expected_version = (repo_root / "VERSION").read_text().strip()
        assert f"hb, version {expected_version}" in result.stdout, result.stdout
