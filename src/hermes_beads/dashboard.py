"""Read-only static dashboard helpers for hermes-beads.

The dashboard is intentionally a derived artifact: it collects public-safe
summaries from Beads/Hermes-shaped records and renders static HTML. It does not
persist data and does not expose control-plane actions.
"""
from __future__ import annotations

import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

PRIVATE_PATTERNS = (
    re.compile(r"/home/|/Users/|C:\\Users\\", re.IGNORECASE),
    re.compile(r"(^|[^0-9])(192\.168\.[0-9]{1,3}\.[0-9]{1,3}|10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[0-1])\.[0-9]{1,3}\.[0-9]{1,3})([^0-9]|$)"),
    re.compile(r"github_pat_|ghp_|BEGIN .*PRIVATE KEY|----BEGIN.*PRIVATE KEY----", re.IGNORECASE),
    re.compile(r"OPENAI_|ANTHROPIC_|DEEPSEEK_|XAI_|AWS_", re.IGNORECASE),
)

PUBLIC_METADATA_KEYS = {
    "hermes_profile",
    "hermes_mode",
    "hermes_status",
    "hermes_iteration",
    "hermes_kanban_task_id",
    "hermes_requires_review",
    "hermes_gate_status",
    "hermes_gate_type",
}


def is_public_safe_text(value: str) -> bool:
    """Return whether text avoids the repository's private-data patterns."""
    return not any(pattern.search(value) for pattern in PRIVATE_PATTERNS)


def assert_public_safe_dashboard(rendered: str) -> None:
    """Raise ``ValueError`` if rendered dashboard output leaks private data."""
    if not is_public_safe_text(rendered):
        raise ValueError("dashboard output contains private data pattern")


def _safe_str(value: Any, *, limit: int = 180) -> str:
    """Return a bounded string suitable for public dashboard rendering."""
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").strip()
    if not is_public_safe_text(text):
        return "[redacted]"
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def collect_dashboard_data(
    beads: Iterable[dict[str, Any]],
    kanban_tasks: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Collect dashboard data without persisting or exposing private fields."""
    task_by_id = {str(task.get("id", "")): task for task in (kanban_tasks or [])}
    items: list[dict[str, Any]] = []
    for bead in beads:
        metadata = bead.get("metadata", {}) or {}
        task_id = str(metadata.get("hermes_kanban_task_id", "") or "")
        public_metadata = {
            key: _safe_str(value)
            for key, value in metadata.items()
            if key in PUBLIC_METADATA_KEYS and value not in (None, "")
        }
        items.append(
            {
                "id": _safe_str(bead.get("id")),
                "title": _safe_str(bead.get("title")),
                "status": _safe_str(bead.get("status")),
                "priority": bead.get("priority", 2),
                "issue_type": _safe_str(bead.get("issue_type")),
                "assignee": _safe_str(bead.get("assignee") or bead.get("owner")),
                "labels": [_safe_str(label) for label in (bead.get("labels", []) or [])],
                "metadata": public_metadata,
                "kanban": {
                    "task_id": _safe_str(task_id),
                    "status": _safe_str(task_by_id.get(task_id, {}).get("status", "")),
                },
            }
        )
    status_counts = Counter(item["status"] for item in items)
    data = {
        "summary": {
            "total": len(items),
            "by_status": dict(sorted(status_counts.items())),
            "ready": status_counts.get("open", 0),
        },
        "items": items,
    }
    return data


def render_dashboard_html(data: dict[str, Any]) -> str:
    """Render a static, public-safe HTML dashboard."""
    summary = data.get("summary", {})
    items = data.get("items", [])
    cards = []
    for item in items:
        labels = " ".join(f"<span class='badge'>{html.escape(str(label))}</span>" for label in item.get("labels", []))
        meta = item.get("metadata", {})
        meta_text = ", ".join(f"{html.escape(str(k))}: {html.escape(str(v))}" for k, v in sorted(meta.items()))
        cards.append(
            "<article class='task-card'>"
            f"<h3>{html.escape(str(item.get('id', '')))} — {html.escape(str(item.get('title', '')))}</h3>"
            f"<p>Status: <strong>{html.escape(str(item.get('status', '')))}</strong> · Priority: {html.escape(str(item.get('priority', '')))}</p>"
            f"<p>Type: {html.escape(str(item.get('issue_type', '')))} · Assignee: {html.escape(str(item.get('assignee', '')))}</p>"
            f"<p>Kanban task: {html.escape(str(item.get('kanban', {}).get('task_id', '')))}</p>"
            f"<p>{labels}</p>"
            f"<p class='metadata'>{html.escape(meta_text)}</p>"
            "</article>"
        )
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hermes-Beads Dashboard</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 2rem; }}
    .summary, .task-card {{ background: rgba(15, 23, 42, .88); border: 1px solid #334155; border-radius: 14px; padding: 1rem; margin: 1rem 0; }}
    .badge {{ display: inline-block; margin: .15rem; padding: .2rem .45rem; border-radius: 999px; background: #1e293b; color: #bfdbfe; }}
    .metadata {{ color: #94a3b8; }}
  </style>
</head>
<body>
<main>
  <h1>Hermes-Beads Dashboard</h1>
  <section class="summary">
    <h2>Summary</h2>
    <p>Total beads: <strong>{html.escape(str(summary.get('total', 0)))}</strong></p>
    <pre>{html.escape(json.dumps(summary.get('by_status', {}), indent=2, sort_keys=True))}</pre>
  </section>
  <section id="ready-work"><h2>Ready Work</h2>{''.join(card for card in cards if 'Status: <strong>open</strong>' in card) or '<p>No open work in this snapshot.</p>'}</section>
  <section id="all-work"><h2>All Work</h2>{''.join(cards) or '<p>No beads found.</p>'}</section>
  <section id="non-goals"><h2>Non-goals</h2><p>This dashboard is read-only. It is not a control plane and performs no Beads or Hermes mutations.</p></section>
</main>
</body>
</html>
"""
    assert_public_safe_dashboard(html_doc)
    return html_doc


def write_dashboard(path: str | Path, data: dict[str, Any]) -> Path:
    """Write the static dashboard HTML to a path and return it."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard_html(data), encoding="utf-8")
    return output
