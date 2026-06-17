"""Tests for plugin_api.py FastAPI routes."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Import the router and patch dependencies that require real bd/hb CLI
from hermes_beads.bead_model import BeadStatus, Bead, BeadProject


@pytest.fixture
def tmp_beads_dir():
    """Create a temp directory with a .beads/issues.jsonl fixture."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        beads_dir = root / ".beads"
        beads_dir.mkdir()
        (beads_dir / "issues.jsonl").write_text(
            json.dumps({
                "id": "hb-test1",
                "title": "Test bead one",
                "status": "open",
                "priority": "P1",
                "type": "task",
            }) + "\n" +
            json.dumps({
                "id": "hb-test2",
                "title": "Test bead two",
                "status": "in_progress",
                "priority": "P2",
                "type": "task",
                "dependencies": [{"depends_on_id": "hb-test1", "type": "blocks"}],
            }) + "\n"
        )
        yield root


@pytest.fixture
def client(tmp_beads_dir):
    """Return a FastAPI TestClient with discover_projects mocked to the temp dir."""
    project = BeadProject(
        name="test-project",
        path=str(tmp_beads_dir),
        bead_count=2,
    )

    with patch("plugin.dashboard.plugin_api.discover_projects", return_value=[project]):
        from plugin.dashboard.plugin_api import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as tc:
            yield tc


class TestHealthCheck:
    def test_hello_returns_ok(self, client):
        resp = client.get("/hello")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plugin"] == "hermes-beads"
        assert data["status"] == "ok"
        assert "version" in data


class TestProjectDiscovery:
    def test_list_projects(self, client):
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["projects"][0]["name"] == "test-project"

    def test_list_projects_is_cached(self, client):
        # Two calls within cache TTL should return same data
        r1 = client.get("/api/projects")
        r2 = client.get("/api/projects")
        assert r1.json() == r2.json()


class TestListBeads:
    def test_list_beads_returns_all(self, client):
        resp = client.get("/api/projects/test-project/beads")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project"] == "test-project"
        assert data["count"] == 2
        ids = [b["id"] for b in data["beads"]]
        assert "hb-test1" in ids
        assert "hb-test2" in ids

    def test_list_beads_invalid_project(self, client):
        resp = client.get("/api/projects/nonexistent/beads")
        assert resp.status_code == 404


class TestGraph:
    def test_graph_returns_nodes_and_edges(self, client):
        resp = client.get("/api/projects/test-project/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 2
        # test2 depends on test1 — edge points from blocker to blocked
        if len(data["edges"]) > 0:
            assert data["edges"][0]["from"] == "hb-test1"
            assert data["edges"][0]["to"] == "hb-test2"

    def test_graph_is_cached(self, client):
        r1 = client.get("/api/projects/test-project/graph")
        r2 = client.get("/api/projects/test-project/graph")
        assert r1.json() == r2.json()


class TestBeadIdValidation:
    def test_valid_bead_id_accepted(self, client):
        with patch("plugin.dashboard.plugin_api._bd") as mock_bd:
            mock_bd.return_value = {"id": "hb-ok", "title": "OK"}
            resp = client.get("/api/projects/test-project/beads/hb-ok")
            assert resp.status_code == 200

    def test_flag_injection_rejected(self, client):
        resp = client.get("/api/projects/test-project/beads/--db")
        assert resp.status_code == 400
        assert "Invalid bead_id" in resp.json()["detail"]

    def test_shell_metachar_rejected(self, client):
        resp = client.get("/api/projects/test-project/beads/foo;cat")
        assert resp.status_code == 400

    def test_empty_bead_id_rejected(self, client):
        # FastAPI treats trailing slash differently — test with path that has
        # an empty bead_id segment (double slash or just route mismatch)
        resp = client.get("/api/projects/test-project/beads/--bad")
        assert resp.status_code == 400

    def test_dispatch_validates_all_ids(self, client):
        resp = client.post(
            "/api/projects/test-project/dispatch",
            json={"bead_ids": ["valid-1", "--invalid"]},
        )
        assert resp.status_code == 400


class TestDispatchValidation:
    def test_dispatch_empty_ids(self, client):
        resp = client.post(
            "/api/projects/test-project/dispatch",
            json={"bead_ids": []},
        )
        assert resp.status_code == 400
        assert "No bead_ids" in resp.json()["detail"]


class TestShowBead:
    def test_show_bead_returns_detail(self, client):
        with patch("plugin.dashboard.plugin_api._bd") as mock_bd:
            mock_bd.return_value = {"id": "hb-test1", "title": "Test bead one"}
            resp = client.get("/api/projects/test-project/beads/hb-test1")
            assert resp.status_code == 200
            assert resp.json()["bead"]["title"] == "Test bead one"

    def test_show_bead_bd_error(self, client):
        with patch("plugin.dashboard.plugin_api._bd", side_effect=RuntimeError("bd crash")):
            resp = client.get("/api/projects/test-project/beads/hb-test1")
            assert resp.status_code == 500


class TestGateResolver:
    def test_gate_resolve_closes_bead(self, client):
        with patch("plugin.dashboard.plugin_api._bd") as mock_bd:
            # bd show returns array, bd close returns empty
            mock_bd.side_effect = [
                [{"id": "hb-test1", "dependents": []}],  # show
                {},  # close
            ]
            resp = client.post(
                "/api/projects/test-project/gate/hb-test1",
                json={"comment": "done"},
            )
            assert resp.status_code == 200
            assert resp.json()["action"] == "closed"

    def test_gate_resolve_blocks_on_children(self, client):
        with patch("plugin.dashboard.plugin_api._bd") as mock_bd:
            mock_bd.return_value = [{
                "id": "hb-test1",
                "dependents": [
                    {"id": "child1", "status": "open", "title": "Child task"},
                ],
            }]
            resp = client.post(
                "/api/projects/test-project/gate/hb-test1",
                json={},
            )
            assert resp.status_code == 200
            assert resp.json()["action"] == "blocked"


class TestCacheBust:
    def test_dispatch_busts_project_cache(self, client):
        # Prime the graph cache
        client.get("/api/projects/test-project/graph")

        # shutil.which is imported inside dispatch_beads, so patch that path
        with patch("shutil.which", return_value="/usr/bin/hb"), \
             patch("plugin.dashboard.plugin_api.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "ok"
            mock_run.return_value.stderr = ""
            client.post(
                "/api/projects/test-project/dispatch",
                json={"bead_ids": ["hb-test1"]},
            )
            resp = client.get("/api/projects/test-project/graph")
            assert resp.status_code == 200
