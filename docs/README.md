# Hermes-Beads Documentation

Hermes-Beads connects [Beads](https://github.com/gastownhall/beads) task state with Hermes agent workflows. The project keeps task state durable, public-safe, and reviewable while Hermes agents remain disposable execution workers.

## Start Here

- [Beads Usage](beads-usage.md) — local task graph commands and conventions.
- [Metadata Schema](metadata-schema.md) — public metadata contract used by agents.
- [Handoff Packet](handoff-packet.md) — JSON context shape passed between Beads and Hermes.
- [Kanban Bridge](kanban-bridge.md) — bridge design and implemented dry-run commands.
- [Product Contract](product-contract.md) — authority model, mutation semantics, idempotency rules.
- [Gate Resolver](gate-resolver.md) — profile routing rules.
- [Beads Compatibility](beads-compatibility.md) — supported setup modes, bd output contract, minimum version.

## Release Gates

The CI workflow verifies privacy scanning, Python tests, non-editable package install behavior, generated GitBook docs, and code doc coverage above 90%.

See the [Release Matrix](release-matrix.md) for the full pre-PyPI gate checklist, sequencing constraints, and versioning policy.
