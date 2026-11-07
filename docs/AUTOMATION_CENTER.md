# Automation Center

Metatron's Automation Center makes recurring work, human approvals and agent execution visible without turning the dashboard into an unrestricted agent-control surface.

## Safety model

Schedules and execution are deliberately separate:

1. A schedule becomes due.
2. Metatron materializes **one Ready Kanban card**, collapsing missed intervals instead of stampeding old work after sleep/resume.
3. An assigned task is started only by an explicit **Run** action.
4. The run gets a persistent execution record.
5. Refresh reconciles the record with the adapter only when the user asks; Metatron does not continuously poll remote agents from the dashboard.

A schedule therefore does **not** silently launch an agent. This is an explicit product invariant.

## Schedules

The Tasks workspace can create interval schedules with a label, interval and optional agent. Schedules can be paused, resumed and deleted. Due schedules preserve their schedule ID and missed-interval count in the materialized task metadata.

## Agent runs

A Ready card with an assigned adapter exposes **Run**. Metatron records:

- task and agent IDs;
- submission metadata returned by the adapter;
- start/finish state;
- last observed adapter state;
- cancellation result and exit state where applicable.

Refresh uses conservative adapter-specific reconciliation:

- Claude Code: result file/state;
- E.O.P./Ezra: job status;
- OpenCode: session status;
- Codex: explicit terminal turn events only.

Metatron never interprets silence as success.

Successful runs move their task to Review. Failed runs move to Blocked. Cancelled runs return the card to Backlog.

## Human approvals

Pending approvals appear beside schedules and runs. Approve/Deny uses the existing persistent approval store so decisions remain auditable.

## Desktop capability boundary

The Automation Center intentionally reuses the already-authorized `tasks.list`, `tasks.create` and `tasks.move` dashboard commands. Automation actions are scoped sub-actions under that contract rather than new privileged command names. The Rust dashboard allowlist therefore remains at the established 35 commands.

## Qualification

Portable tests verify schedule pause/resume/delete, drift-free materialization, no automatic agent execution, explicit run persistence and terminal reconciliation. The product/security audit separately verifies the dashboard allowlist and command implementation.
