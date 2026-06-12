"""Regression tests for the privacy scan script."""
from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN = REPO_ROOT / "scripts" / "scan-privacy.sh"


def test_privacy_scan_does_not_treat_timestamp_fraction_as_private_ip(tmp_path: Path) -> None:
    """A Beads interaction timestamp like 19:06:10.358 is not an IPv4 address."""
    sample = tmp_path / "interactions.jsonl"
    sample.write_text(
        '{"created_at":"2026-06-12T19:06:10.358137221Z","field":"status"}\n'
    )

    result = subprocess.run(
        ["bash", str(SCAN), str(sample)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_privacy_scan_blocks_private_ipv4_address(tmp_path: Path) -> None:
    """The stricter private-IP regex still catches real RFC1918 dotted quads."""
    sample = tmp_path / "unsafe.txt"
    private_ip = ".".join(["10", "1", "2", "3"])
    sample.write_text(f"connect to {private_ip} for debugging\n")

    result = subprocess.run(
        ["bash", str(SCAN), str(sample)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "BLOCKED" in result.stdout
    assert private_ip in result.stdout
