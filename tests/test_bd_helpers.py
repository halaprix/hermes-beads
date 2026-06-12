"""Tests for bd CLI helpers — error handling, preflight checks, JSON parsing."""
from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import click
import pytest

from hermes_beads.bd_helpers import check_bd_available, run_bd, run_bd_json


# ---------------------------------------------------------------------------
# check_bd_available
# ---------------------------------------------------------------------------


class TestCheckBdAvailable:
    """Preflight check for whether bd is on PATH."""

    def test_bd_on_path(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/bd"):
            check_bd_available()  # should not raise

    def test_bd_not_on_path(self) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(click.ClickException, match="bd command not found"):
                check_bd_available()

    def test_bd_on_path_respects_which_result(self) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            check_bd_available()  # should not raise


# ---------------------------------------------------------------------------
# run_bd
# ---------------------------------------------------------------------------


class TestRunBd:
    """Text-output wrapper around bd subprocess calls."""

    def test_success(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="bd 1.0.0\n", stderr="")
            result = run_bd(["version"])
            assert result == "bd 1.0.0\n"

    def test_missing_bd_via_shell(self) -> None:
        """When bd is absent, shell returns exit 127 with 'command not found'."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                127,
                ["bd", "version"],
                stderr="bd: command not found",
            )
            with pytest.raises(click.ClickException, match="bd: command not found"):
                run_bd(["version"])

    def test_non_zero_exit(self) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/bd"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.side_effect = subprocess.CalledProcessError(
                1,
                ["bd", "show", "nonexistent"],
                stderr="Error: no bead found with id 'nonexistent'\n",
            )
            with pytest.raises(click.ClickException) as exc_info:
                run_bd(["show", "nonexistent"])
            assert "bd show nonexistent failed" in str(exc_info.value)
            assert "no bead found" in str(exc_info.value)

    def test_non_zero_exit_no_stderr(self) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/bd"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.side_effect = subprocess.CalledProcessError(
                1, ["bd", "badcmd"], stderr=""
            )
            with pytest.raises(click.ClickException) as exc_info:
                run_bd(["badcmd"])
            assert "bd badcmd failed" in str(exc_info.value)

    def test_file_not_found_fallback(self) -> None:
        """If shutil.which lies or bd is deleted between check and run."""
        with (
            patch("shutil.which", return_value="/usr/bin/bd"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.side_effect = FileNotFoundError("No such file")
            with pytest.raises(click.ClickException, match="bd command not found"):
                run_bd(["version"])


# ---------------------------------------------------------------------------
# run_bd_json
# ---------------------------------------------------------------------------


class TestRunBdJson:
    """JSON-output wrapper around bd subprocess calls."""

    def test_success(self) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/bd"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(
                stdout='{"id": "hb-test", "status": "open"}\n', stderr=""
            )
            result = run_bd_json(["show", "hb-test", "--json"])
            assert result == {"id": "hb-test", "status": "open"}

    def test_empty_stdout_returns_none(self) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/bd"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(stdout="", stderr="")
            result = run_bd_json(["version"])
            assert result is None

    def test_null_json_returns_none(self) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/bd"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(stdout="null\n", stderr="")
            result = run_bd_json(["version"])
            assert result is None

    def test_invalid_json(self) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/bd"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(
                stdout="this is not json\n", stderr=""
            )
            with pytest.raises(click.ClickException) as exc_info:
                run_bd_json(["ready", "--json"])
            assert "invalid json" in str(exc_info.value).lower()
            assert "this is not json" in str(exc_info.value)

    def test_invalid_json_trimmed_output(self) -> None:
        """Long output should be truncated in the error message."""
        long_output = "x" * 500
        with (
            patch("shutil.which", return_value="/usr/bin/bd"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(stdout=long_output, stderr="")
            with pytest.raises(click.ClickException) as exc_info:
                run_bd_json(["ready", "--json"])
            msg = str(exc_info.value)
            assert "invalid json" in msg.lower()
            assert len(msg) < 600  # shouldn't bloat with the full 500 chars

    def test_non_zero_exit(self) -> None:
        with (
            patch("shutil.which", return_value="/usr/bin/bd"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.side_effect = subprocess.CalledProcessError(
                1,
                ["bd", "ready", "--json"],
                stderr="Error: no ready beads\n",
            )
            with pytest.raises(click.ClickException) as exc_info:
                run_bd_json(["ready", "--json"])
            assert "bd ready --json failed" in str(exc_info.value)
            assert "no ready beads" in str(exc_info.value)
