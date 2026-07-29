"""
Pydantic models for Beads data.

Represents the bead issue graph in a structured, typed format.
Consumed by the dashboard plugin API and the data reader layer.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class BeadStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    CLOSED = "closed"
    DEFERRED = "deferred"


class BeadPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class BeadDependency(BaseModel):
    """A single dependency edge between two beads."""

    issue_id: str = Field(alias="id", default="")
    depends_on_id: str = ""
    type: str = "blocks"


class Bead(BaseModel):
    """A single bead (issue) from the Beads issue tracker."""

    id: str
    title: str = ""
    description: str = ""
    status: BeadStatus = BeadStatus.OPEN
    priority: BeadPriority = BeadPriority.P1
    issue_type: str = Field(default="task", alias="type")
    assignee: str = ""
    owner: str = ""
    estimated_minutes: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: str = ""
    dependencies: list[BeadDependency] = Field(default_factory=list)
    dependency_count: int = 0
    dependent_count: int = 0
    comment_count: int = 0

    # Resolved fields (set by reader after parsing)
    tags: list[str] = Field(default_factory=list)
    project: str = ""

    model_config = {"populate_by_name": True}

    @property
    def blockers(self) -> list[str]:
        """Bead IDs that block this bead."""
        return [d.depends_on_id for d in self.dependencies if d.type == "blocks"]

    @property
    def is_ready(self) -> bool:
        return self.status == BeadStatus.OPEN and not self.blockers


class BeadGraph(BaseModel):
    """Full bead graph for a project — nodes + edges for vis-network."""

    project: str = ""
    nodes: list[BeadNode] = Field(default_factory=list)
    edges: list[BeadEdge] = Field(default_factory=list)


class BeadNode(BaseModel):
    """A node in the vis-network bead graph."""

    id: str
    label: str = ""
    title: str = ""
    status: BeadStatus = BeadStatus.OPEN
    priority: BeadPriority = BeadPriority.P1
    group: str = ""  # vis-network group for colouring


class BeadEdge(BaseModel):
    """An edge in the vis-network bead graph."""

    from_: str = Field(alias="from")
    to: str
    arrows: str = "to"
    dep_type: str = Field(default="blocks", alias="type")

    model_config = {"populate_by_name": True}


class BeadProject(BaseModel):
    """A discovered Beads project/workspace."""

    name: str
    path: str
    bead_count: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
