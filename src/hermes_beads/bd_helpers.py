"""Helpers for invoking the bd CLI with consistent error handling.

Wraps ``subprocess`` calls so that every failure path — missing binary,
non-zero exit, or invalid JSON — surfaces as a ``click.ClickException``
with an actionable message and the subprocess stderr preserved.
"""
from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from typing import Any

import click


def check_bd_available() -> None:
    """Check that ``bd`` is on ``PATH``.

    Raises
    ------
    click.ClickException
        If ``shutil.which("bd")`` returns ``None``.
    """
    if shutil.which("bd") is None:
        raise click.ClickException(
            "bd command not found on PATH. Is beads CLI installed?"
        )


def run_bd(args: list[str]) -> str:
    """Run ``bd`` with the given *args* and return stdout as text.

    Parameters
    ----------
    args:
        List of command-line arguments passed after ``bd``.

    Returns
    -------
    str
        Captured stdout from the process.

    Raises
    ------
    click.ClickException
        If ``bd`` is not available on ``PATH``, the process exits with a
        non-zero status code, or ``FileNotFoundError`` is raised at
        invocation time (belt-and-suspenders guard).
    """
    try:
        result = subprocess.run(
            ["bd", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        raise click.ClickException(
            "bd command not found on PATH. Is beads CLI installed?"
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        cmd = shlex.join(args)
        msg = f"bd {cmd} failed"
        if stderr:
            msg += f": {stderr}"
        raise click.ClickException(msg)
    return result.stdout


def run_bd_json(args: list[str]) -> Any:
    """Run ``bd`` with the given *args* and return parsed JSON output.

    Parameters
    ----------
    args:
        List of command-line arguments passed after ``bd``.

    Returns
    -------
    Any
        The JSON-decoded value (usually a ``dict`` or ``list``, or
        ``None`` for empty/null output).

    Raises
    ------
    click.ClickException
        If ``bd`` fails or returns output that cannot be parsed as JSON.
    """
    stdout = run_bd(args)
    try:
        return json.loads(stdout or "null")
    except json.JSONDecodeError as exc:
        snippet = (stdout[:200] + "...") if len(stdout or "") > 200 else (stdout or "<empty>")
        raise click.ClickException(
            f"bd {shlex.join(args)} returned invalid JSON: {exc}. "
            f"Output: {snippet}"
        )
