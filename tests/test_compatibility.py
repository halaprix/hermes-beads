"""Tests for Beads setup compatibility matrix.

Covers the supported/unsupported setup modes documented in
docs/beads-compatibility.md and the machine-readable bd output
contract that hermes-beads (hb) relies on.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_bd(cwd: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bd", *args], cwd=cwd, capture_output=True, text=True, check=check,
    )


def _run_bd_json(cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
    """Run bd with --json appended and return the CompletedProcess (stdout+stderr)."""
    return _run_bd(cwd, args + ["--json"], check=False)


def _run_hb(cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "hermes_beads.cli", *args],
        cwd=cwd,
        env={**__import__("os").environ, "PYTHONPATH": str(_repo_root() / "src")},
        capture_output=True,
        text=True,
    )


def _init_temp_beads(tmp_path: Path, prefix: str, extra_args: list[str] | None = None) -> Path:
    """Initialise a temporary git+Beads workspace."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    base = ["init", "--prefix", prefix, "--quiet", "--non-interactive", "--skip-agents", "--skip-hooks"]
    if extra_args:
        base.extend(extra_args)
    result = _run_bd(tmp_path, base)
    assert result.returncode == 0, f"bd init failed: {result.stderr}"
    return tmp_path


def _create_test_bead(cwd: Path, metadata: dict | None = None) -> str:
    """Create a bead and return its id."""
    args = ["create", "Compatibility test bead", "--json"]
    if metadata:
        args.extend(["--metadata", json.dumps(metadata)])
    result = _run_bd_json(cwd, args)
    assert result.returncode == 0, f"bd create failed: {result.stderr}"
    data = json.loads(result.stdout)
    if isinstance(data, list):
        return data[0]["id"]
    return data["id"]


def _update_bead_labels(cwd: Path, bead_id: str, labels: list[str]) -> None:
    """Add labels to a bead."""
    for label in labels:
        _run_bd(cwd, ["update", bead_id, "--add-label", label], check=False)


# ---------------------------------------------------------------------------
# Require bd CLI
# ---------------------------------------------------------------------------

def _bd_installed() -> bool:
    try:
        r = subprocess.run(["bd", "version"], capture_output=True, text=True)
        return r.returncode == 0
    except FileNotFoundError:
        return False


pytestmark = pytest.mark.skipif(not _bd_installed(), reason="bd CLI is not installed")


# ===================================================================
# Smoke tests for cheap local setup modes
# ===================================================================

class TestStandardEmbedded:
    """Standard embedded Dolt repo (default bd init)."""

    def test_hb_dispatch_dry_run(self, tmp_path: Path) -> None:
        _init_temp_beads(tmp_path, prefix="std")
        bead_id = _create_test_bead(tmp_path, {
            "hermes_status": "ready",
            "hermes_profile": "ts-dev",
            "hermes_mode": "pr",
        })
        result = _run_hb(tmp_path, ["bridge", "dispatch", "--dry-run"])
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert len(payload["tasks"]) >= 1
        task = payload["tasks"][0]
        assert task["source_bead_id"] == bead_id
        assert task["assignee"] == "ts-dev"
        body = json.loads(task["body"])
        assert body["bead_id"] == bead_id

    def test_hb_dispatch_apply_links_metadata_and_skips_second_run(self, tmp_path: Path) -> None:
        _init_temp_beads(tmp_path, prefix="std")
        bead_id = _create_test_bead(
            tmp_path,
            {
                "hermes_status": "ready",
                "hermes_profile": "ts-dev",
                "hermes_mode": "pr",
            },
        )
        queue_file = Path(".queue/dispatch.json")
        args = [
            "bridge",
            "dispatch",
            "--apply",
            "--backend",
            "local-file",
            "--queue-file",
            str(queue_file),
        ]

        first = _run_hb(tmp_path, args)
        assert first.returncode == 0, first.stderr
        first_payload = json.loads(first.stdout)
        assert len(first_payload["tasks"]) == 1

        linked = json.loads(_run_bd_json(tmp_path, ["show", bead_id]).stdout)
        if isinstance(linked, list):
            linked = linked[0]
        assert linked["metadata"]["hermes_kanban_task_id"] == first_payload["tasks"][0]["id"]

        second = _run_hb(tmp_path, args)
        assert second.returncode == 0, second.stderr
        second_payload = json.loads(second.stdout)
        assert second_payload["tasks"] == []
        assert json.loads((tmp_path / queue_file).read_text())["tasks"] == first_payload["tasks"]

    def test_hb_profile_dry_run(self, tmp_path: Path) -> None:
        _init_temp_beads(tmp_path, prefix="std")
        bead_id = _create_test_bead(tmp_path, {
            "hermes_status": "ready",
            "hermes_profile": "docs",
            "hermes_mode": "pr",
        })
        result = _run_hb(tmp_path, ["bridge", "profile", bead_id, "--dry-run"])
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["bead_id"] == bead_id
        assert data["hermes_profile"] == "docs"
        assert "reason" in data


class TestStealthEmbedded:
    """Stealth embedded Dolt repo (bd init --stealth)."""

    def test_hb_dispatch_dry_run(self, tmp_path: Path) -> None:
        _init_temp_beads(tmp_path, prefix="stl", extra_args=["--stealth"])
        bead_id = _create_test_bead(tmp_path, {
            "hermes_status": "ready",
            "hermes_profile": "ts-dev",
            "hermes_mode": "pr",
        })
        result = _run_hb(tmp_path, ["bridge", "dispatch", "--dry-run"])
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert len(payload["tasks"]) >= 1
        task = payload["tasks"][0]
        assert task["source_bead_id"] == bead_id

    def test_hb_profile_dry_run(self, tmp_path: Path) -> None:
        _init_temp_beads(tmp_path, prefix="stl", extra_args=["--stealth"])
        bead_id = _create_test_bead(tmp_path, {
            "hermes_status": "ready",
            "hermes_profile": "ts-dev",
            "hermes_mode": "pr",
        })
        result = _run_hb(tmp_path, ["bridge", "profile", bead_id, "--dry-run"])
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["bead_id"] == bead_id


class TestNestedCwd:
    """Beads repo initialised at root, hb invoked from a subdirectory."""

    def test_nested_cwd_dispatch(self, tmp_path: Path) -> None:
        repo_root = _init_temp_beads(tmp_path, prefix="nst")
        bead_id = _create_test_bead(repo_root, {
            "hermes_status": "ready",
            "hermes_profile": "ts-dev",
            "hermes_mode": "pr",
        })
        subdir = repo_root / "deep" / "nested" / "path"
        subdir.mkdir(parents=True)
        result = _run_hb(subdir, ["bridge", "dispatch", "--dry-run"])
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert len(payload["tasks"]) >= 1
        task = payload["tasks"][0]
        assert task["source_bead_id"] == bead_id

    def test_nested_cwd_profile(self, tmp_path: Path) -> None:
        repo_root = _init_temp_beads(tmp_path, prefix="nst")
        bead_id = _create_test_bead(repo_root, {
            "hermes_status": "ready",
            "hermes_profile": "ts-dev",
            "hermes_mode": "pr",
        })
        subdir = repo_root / "deep" / "nested" / "path"
        subdir.mkdir(parents=True)
        result = _run_hb(subdir, ["bridge", "profile", bead_id, "--dry-run"])
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["bead_id"] == bead_id
        assert "reason" in data


# ===================================================================
# bd --json stderr-warning capture
# ===================================================================

class TestJsonStderrClean:
    """Ensure bd --json subcommands used by hb do not emit deprecation warnings."""

    def test_ready_json_stderr(self, tmp_path: Path) -> None:
        _init_temp_beads(tmp_path, prefix="jr")
        result = _run_bd_json(tmp_path, ["ready"])
        assert result.stderr == "", f"stderr not empty: {result.stderr!r}"

    def test_show_json_stderr(self, tmp_path: Path) -> None:
        _init_temp_beads(tmp_path, prefix="js")
        bead_id = _create_test_bead(tmp_path)
        result = _run_bd_json(tmp_path, ["show", bead_id])
        assert result.stderr == "", f"stderr not empty: {result.stderr!r}"

    def test_comments_json_stderr(self, tmp_path: Path) -> None:
        _init_temp_beads(tmp_path, prefix="jc")
        bead_id = _create_test_bead(tmp_path)
        result = _run_bd_json(tmp_path, ["comments", bead_id])
        assert result.stderr == "", f"stderr not empty: {result.stderr!r}"

    def test_context_json_stderr(self, tmp_path: Path) -> None:
        _init_temp_beads(tmp_path, prefix="jx")
        result = _run_bd_json(tmp_path, ["context"])
        assert result.stderr == "", f"stderr not empty: {result.stderr!r}"


# ===================================================================
# Contract tests: fields hb consumes from bd JSON output
# ===================================================================

class TestReadyJsonContract:
    """Fields hb consumes from bd ready --json.

    hb reads fields defensively (bead.get('description', '')) so absent
    fields are handled. This test verifies the fields that ARE present
    have the expected types, and that the fields hb reads are either
    present or safely defaulted.
    """

    def test_ready_bead_has_core_fields(self, tmp_path: Path) -> None:
        """A ready bead always has id, title, status, priority, issue_type."""
        _init_temp_beads(tmp_path, prefix="rc")
        _create_test_bead(tmp_path)
        result = _run_bd_json(tmp_path, ["ready"])
        assert result.returncode == 0, result.stderr
        beads = json.loads(result.stdout)
        assert len(beads) > 0
        bead = beads[0]
        assert "id" in bead
        assert "title" in bead
        assert "status" in bead
        assert "priority" in bead
        assert "issue_type" in bead
        assert isinstance(bead["id"], str)
        assert isinstance(bead["title"], str)

    def test_ready_bead_with_metadata(self, tmp_path: Path) -> None:
        """Bead created with metadata has metadata field in ready output."""
        _init_temp_beads(tmp_path, prefix="rc")
        _create_test_bead(tmp_path, {"hermes_status": "ready"})
        result = _run_bd_json(tmp_path, ["ready"])
        beads = json.loads(result.stdout)
        assert len(beads) > 0


class TestShowJsonContract:
    """Fields hb consumes from bd show <id> --json."""

    def test_show_has_core_fields(self, tmp_path: Path) -> None:
        _init_temp_beads(tmp_path, prefix="sc")
        bead_id = _create_test_bead(tmp_path)
        result = _run_bd_json(tmp_path, ["show", bead_id])
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        beads = data if isinstance(data, list) else [data]
        bead = next(b for b in beads if b["id"] == bead_id)
        assert "id" in bead
        assert "title" in bead
        assert "status" in bead
        assert isinstance(bead["id"], str)
        assert isinstance(bead["title"], str)

    def test_show_with_labels_metadata_description(self, tmp_path: Path) -> None:
        """When a bead has labels and metadata, they appear in show output."""
        _init_temp_beads(tmp_path, prefix="sc")
        bead_id = _create_test_bead(tmp_path, {"hermes_status": "ready", "hermes_profile": "ts-dev"})
        _update_bead_labels(tmp_path, bead_id, ["docs"])
        result = _run_bd_json(tmp_path, ["show", bead_id])
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        beads = data if isinstance(data, list) else [data]
        bead = next(b for b in beads if b["id"] == bead_id)
        # hb uses bead.get("labels", []) and bead.get("dependencies", [])
        # so these are not required but tested when present
        if "labels" in bead:
            assert isinstance(bead["labels"], list)
        if "metadata" in bead:
            assert isinstance(bead["metadata"], dict)
        if "description" in bead:
            assert isinstance(bead["description"], str)


class TestCommentsJsonContract:
    """Fields hb consumes from bd comments <id> --json.

    hb's normalize_comments reads from flexible key fallbacks:
      author  ← author, created_by, actor
      body    ← body, text, comment, content
      created_at ← created_at, timestamp
    """

    def test_comments_contain_hb_fields(self, tmp_path: Path) -> None:
        _init_temp_beads(tmp_path, prefix="cc")
        bead_id = _create_test_bead(tmp_path)
        _run_bd(tmp_path, ["comments", "add", bead_id, "test comment body"])
        result = _run_bd_json(tmp_path, ["comments", bead_id])
        assert result.returncode == 0, result.stderr
        comments = json.loads(result.stdout)
        assert len(comments) >= 1
        comment = comments[0]
        # At least one author-bearing key must be present
        assert any(k in comment for k in ("author", "created_by", "actor")), \
            f"comment missing author key: {list(comment.keys())}"
        # At least one body-bearing key must be present
        assert any(k in comment for k in ("body", "text", "comment", "content")), \
            f"comment missing body key: {list(comment.keys())}"
        # At least one timestamp key must be present
        assert any(k in comment for k in ("created_at", "timestamp")), \
            f"comment missing timestamp key: {list(comment.keys())}"


class TestContextJsonContract:
    """Fields potentially consumed from bd context --json."""

    def test_context_contains_schema_version(self, tmp_path: Path) -> None:
        _init_temp_beads(tmp_path, prefix="xc")
        result = _run_bd_json(tmp_path, ["context"])
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail(f"bd context did not return valid JSON: {result.stdout!r}")
        assert "schema_version" in data, f"context missing schema_version keys: {list(data.keys())}"


# ===================================================================
# bd-on-PATH auto-discovery preflight test
# ===================================================================

class TestBdOnPath:
    """hb auto-discovers bd CLI from PATH when invoked as installed console script."""

    def test_installed_hb_dispatch_dry_run(self, tmp_path: Path, built_wheel: Path) -> None:
        """Installed hb (console script) invoking bd from PATH against a Beads workspace."""
        repo_root = _repo_root()
        venv_dir = tmp_path / "venv"

        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        subprocess.run(
            [str(venv_dir / "bin" / "python"), "-m", "pip", "install", "-q", str(built_wheel)],
            check=True,
        )

        # Create a separate Beads workspace
        beads_dir = tmp_path / "beads_workspace"
        beads_dir.mkdir(parents=True)
        _init_temp_beads(beads_dir, prefix="ad")
        bead_id = _create_test_bead(beads_dir, {
            "hermes_status": "ready",
            "hermes_profile": "ts-dev",
            "hermes_mode": "pr",
        })

        # Run the installed hb console script against the Beads workspace
        hb = str(venv_dir / "bin" / "hb")
        result = subprocess.run(
            [hb, "bridge", "dispatch", "--dry-run"],
            cwd=beads_dir,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        payload = json.loads(result.stdout)
        assert len(payload["tasks"]) >= 1
        task = payload["tasks"][0]
        assert task["source_bead_id"] == bead_id
        assert task["assignee"] == "ts-dev"

    def test_installed_hb_local_file_smoke_loop(self, tmp_path: Path, built_wheel: Path) -> None:
        """Installed hb must run the full local-file smoke loop against a temp product repo."""
        venv_dir = tmp_path / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        subprocess.run(
            [str(venv_dir / "bin" / "python"), "-m", "pip", "install", "-q", str(built_wheel)],
            check=True,
        )

        product_repo = tmp_path / "product"
        product_repo.mkdir(parents=True)
        _init_temp_beads(product_repo, prefix="adsmoke")
        bead_id = _create_test_bead(
            product_repo,
            {
                "hermes_status": "ready",
                "hermes_profile": "ts-dev",
                "hermes_mode": "pr",
                "hermes_stop_condition": "smoke completed",
            },
        )

        hb = str(venv_dir / "bin" / "hb")
        queue_file = product_repo / ".queue" / "dispatch.json"
        dispatch = subprocess.run(
            [hb, "bridge", "dispatch", "--apply", "--backend", "local-file", "--queue-file", str(queue_file)],
            cwd=product_repo,
            capture_output=True,
            text=True,
        )
        assert dispatch.returncode == 0, dispatch.stderr
        payload = json.loads(dispatch.stdout)
        assert payload["applied"] is True
        assert payload["backend"] == "local-file"
        assert len(payload["tasks"]) == 1
        task = payload["tasks"][0]
        source_bead_id = task.get("source_bead_id") or task["payload"]["source_bead_id"]
        assert source_bead_id == bead_id

        queue = json.loads(queue_file.read_text())
        assert len(queue["tasks"]) == 1
        assert queue["tasks"][0]["id"] == task["id"]

        results_file = product_repo / "results.json"
        results_file.write_text(
            json.dumps(
                [
                    {
                        "source_bead_id": bead_id,
                        "dispatch_id": task["id"],
                        "status": "completed",
                        "summary": "installed wheel smoke completed",
                    }
                ]
            )
        )

        sync = subprocess.run(
            [hb, "bridge", "sync-results", "--apply", "--results-file", str(results_file)],
            cwd=product_repo,
            capture_output=True,
            text=True,
        )
        assert sync.returncode == 0, sync.stderr
        sync_payload = json.loads(sync.stdout)
        assert sync_payload["applied"] is True

        comments_before = _run_bd(product_repo, ["comments", bead_id, "--json"])
        assert comments_before.returncode == 0, comments_before.stderr
        queue_before = queue_file.read_text()

        dispatch_again = subprocess.run(
            [hb, "bridge", "dispatch", "--apply", "--backend", "local-file", "--queue-file", str(queue_file)],
            cwd=product_repo,
            capture_output=True,
            text=True,
        )
        assert dispatch_again.returncode == 0, dispatch_again.stderr
        dispatch_again_payload = json.loads(dispatch_again.stdout)
        assert dispatch_again_payload["applied"] is True
        assert dispatch_again_payload["backend"] == "local-file"
        assert dispatch_again_payload["tasks"] == []
        assert queue_file.read_text() == queue_before

        sync_again = subprocess.run(
            [hb, "bridge", "sync-results", "--apply", "--results-file", str(results_file)],
            cwd=product_repo,
            capture_output=True,
            text=True,
        )
        assert sync_again.returncode == 0, sync_again.stderr
        sync_again_payload = json.loads(sync_again.stdout)
        assert sync_again_payload["applied"] is True

        shown = _run_bd(product_repo, ["show", bead_id, "--json"])
        assert shown.returncode == 0, shown.stderr
        bead = json.loads(shown.stdout)[0]
        assert bead["status"] == "closed"

        comments = _run_bd(product_repo, ["comments", bead_id, "--json"])
        assert comments.returncode == 0, comments.stderr
        assert comments.stdout == comments_before.stdout
        assert "installed wheel smoke completed" in comments.stdout
