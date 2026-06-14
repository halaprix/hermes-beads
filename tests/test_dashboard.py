"""Tests for static dashboard helpers."""

from __future__ import annotations

import pytest

from hermes_beads.dashboard import assert_public_safe_dashboard, collect_dashboard_data, render_dashboard_html


def test_dashboard_collector_shape_has_no_private_fields() -> None:
    data = collect_dashboard_data(
        [
            {
                "id": "hb-a",
                "title": "Build feature",
                "status": "open",
                "priority": 1,
                "issue_type": "task",
                "description": "internal details should not be copied",
                "metadata": {
                    "hermes_profile": "ts-dev",
                    "private_path": "redacted by omission",
                    "hermes_kanban_task_id": "t_123",
                },
                "labels": ["roadmap"],
            }
        ]
    )
    assert data["summary"]["total"] == 1
    assert data["items"][0]["id"] == "hb-a"
    assert "description" not in data["items"][0]
    assert "private_path" not in data["items"][0]["metadata"]


def test_dashboard_render_contains_invariant_sections() -> None:
    data = collect_dashboard_data([{"id": "hb-a", "title": "Task", "status": "open", "metadata": {}}])
    rendered = render_dashboard_html(data)
    assert "Hermes-Beads Dashboard" in rendered
    assert "Summary" in rendered
    assert "Ready Work" in rendered
    assert "All Work" in rendered
    assert "not a control plane" in rendered


def test_dashboard_privacy_fails_on_unsafe_fixture() -> None:
    unsafe = "/ho" + "me/example/project"
    with pytest.raises(ValueError):
        assert_public_safe_dashboard(unsafe)


def test_dashboard_privacy_passes_on_sanitized_fixture() -> None:
    assert_public_safe_dashboard("workspace <project-root>/repo and task hb-a")
