# Advanced Gates and Human-in-Loop Workflow

Advanced gates let Beads express that a task must pause for approval, review, or retry escalation before more autonomous work continues.

## Metadata contract

All gate metadata is public-safe and lives on the bead:

| Field | Meaning |
| --- | --- |
| `hermes_requires_approval` | `true` when a human approval gate is active |
| `hermes_gate_status` | `pending` or `approved` |
| `hermes_gate_type` | `human-approval`, `retry-escalation`, or project-specific public value |
| `hermes_gate_reason` | Short public reason shown to the operator |
| `hermes_requires_review` | Routes the bead to the `reviewer` profile when no explicit profile is set |
| `hermes_retry_escalation_threshold` | Failure iteration count at which sync-results adds an approval gate |

Explicit `metadata.hermes_profile` still wins. Otherwise review labels (`review`, `requires-review`, `pr-gated`, `reviewer`) or `hermes_requires_review=true` route to `reviewer`.

## Commands

```bash
hb gates list --dry-run
hb gates approve <bead-id> --dry-run
hb bridge profile <bead-id> --dry-run
```

The gate commands are dry-run only in this release. They show the mutation plan without changing Beads state. This prevents accidental approval bypass from automation.

## Anti-bypass rules

- A pending approval gate is resolved by an explicit operator action, not by a worker deciding it is done.
- Retry escalation is idempotent because result-sync operation IDs prevent the same failed result from incrementing iteration twice.
- Review routing is advisory until the task is dispatched; explicit metadata can override it for emergency recovery.
- Gate examples must not include private paths, private network addresses, tokens, or hostnames.

## Retry escalation

When a failed result reaches the retry threshold, `hb bridge sync-results` adds these metadata fields in the same update operation as retry bookkeeping:

```json
{
  "hermes_status": "failed",
  "hermes_iteration": 3,
  "hermes_gate_status": "pending",
  "hermes_gate_type": "retry-escalation",
  "hermes_requires_approval": "true",
  "hermes_gate_reason": "retry threshold reached: 3"
}
```

The default threshold is `3`. A bead can override it with `metadata.hermes_retry_escalation_threshold`.

## Human-in-loop loop

A Hermes cron job can periodically run:

```bash
hb gates list --dry-run
```

If gates are present, Hermes can notify the operator with the bead ID, title, gate type, and reason. Approval still requires an explicit follow-up command or future apply-mode implementation; the dashboard remains read-only and never approves gates.
