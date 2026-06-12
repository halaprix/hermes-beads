# Roadmap

## Overview

hermes-beads is a task orchestration system built on beads, designed to bridge Hermes agents with external systems like kanban boards and gate-based resolvers.

## Phase 1: Bootstrap

Establish the foundational project structure and governance.

- README and project documentation
- Guardrails and safety documentation
- Governance documents (this roadmap, contributing guide, changelog)
- Beads usage documentation
- Metadata schema for bead tasks

## Phase 2: Hermes Kanban Bridge

Enable bidirectional sync between beads tasks and external kanban systems.

- Dispatch bridge: `bd ready` → kanban task creation
- Write-back mechanism: kanban status → bead updates
- Status synchronization protocol

## Phase 3: Gate Resolver

Implement gate-based agent handoff using beads as a signal router.

- Gate definition and configuration
- Signal routing between agents
- Conditional handoff logic

## Phase 4: Dashboard

Live dashboard for project state and agent health monitoring.

- Real-time project state visualization
- Agent health metrics
- Task progress and bottleneck identification

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get involved. All changes go through pull requests and are tracked via beads issues (`hb-XXX`).
