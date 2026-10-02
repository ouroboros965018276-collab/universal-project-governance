# Adaptive Report and Evidence Lifecycle

Load this reference when deciding whether to persist a Change Note, Engineering Report, Agent Execution
Audit, Handoff Snapshot, or release Audit.

## Goal

Evidence must be useful enough for review and handoff without making small changes pay a large token,
file-count, or maintenance tax.

Reporting therefore depends on **risk, scale, handoff need, user intent, and observability mode**.

## Observability modes

### minimal

Use when the user explicitly wants low overhead and the task is low risk.

- trivial changes: no standalone report;
- concise final response + VCS diff/commit can be enough;
- current-state docs are still updated when truth changed;
- Engineering/Audit evidence still appears when risk requires it.

### standard — default

- trivial edits: no standalone report by default;
- small meaningful changes: a compact Change Note may be kept in an existing chronology/changelog,
  rather than a new file;
- non-trivial or high-risk changes: Engineering Report;
- real agent/session transition: current Handoff Snapshot;
- release/RC/stable promotion: Audit Report.

### evaluation

Use while testing the Skill, investigating a governance failure, or when the user explicitly wants
evidence to send for external audit.

- normal report selection still applies;
- qualifying non-trivial tasks also generate an Agent Execution Audit;
- governance feedback is captured when useful;
- recent execution evidence is retained within configured bounds.

Evaluation mode is intentionally richer and should not become the public default for every project.

## Report level selection

Numeric thresholds are signals, not substitutes for domain risk.

### No standalone report / compact Change Note

Normally appropriate when all are true:

- low-risk change;
- no migration, security, data-integrity, architecture, schema/API, deployment, or compatibility impact;
- no destructive cleanup requiring proof;
- small scope (for example, a few files and modest line change);
- no handoff or external-audit request.

A Change Note can be only:

- Changed
- Reason
- Validation

Do not create a new persistent file solely to hold three lines if an existing chronology or commit
already provides the durable evidence.

### Engineering Report

Generate when any strong signal applies:

- refactor or architecture change;
- migration/cutover;
- security/privacy-sensitive change;
- API/schema/database/contract change;
- meaningful infrastructure/deployment change;
- destructive cleanup with non-trivial deletion evidence;
- broad change (default heuristic: more than 10 files or more than 300 changed lines);
- significant rollback/recovery implications;
- user explicitly requests an engineering report.

Use `assets/templates/ENGINEERING_REPORT.md`.

### Audit Report

Generate for:

- release candidate;
- stable release;
- major governance/version transition;
- explicit formal audit request.

Release audits are frozen evidence for that candidate/release and must not double as current-state
documentation.

## Agent Execution Audit

Generate when:

- mode is `evaluation` and the task is Engineering/Audit level;
- the user explicitly requests execution evidence;
- a validation failure, rollback, handoff failure, or user correction makes the execution itself
  important evidence.

It records observable actions and evidence, **not private chain-of-thought**.

Use `assets/templates/AGENT_EXECUTION_AUDIT.md`.

## Handoff Snapshot

Generate/refresh only when there is an actual continuation boundary:

- another AI/engineer will take over;
- work is intentionally incomplete;
- important constraints/risks changed;
- next actions need to survive the conversation;
- user explicitly requests a handoff.

The snapshot is **current state**. Overwrite it when handoff state changes; do not accumulate one file
per handoff unless the project has a separate audit requirement.

## Default lifecycle

| Evidence type | Default lifecycle |
|---|---|
| Current project/module state | overwrite/current truth |
| Handoff Snapshot | overwrite/current truth |
| Change Note | existing chronology or VCS; avoid new standalone file when trivial |
| Engineering Report | retain while useful; fold durable facts into current truth; archive/remove when no longer needed unless audit value remains |
| Agent Execution Audit | evaluation evidence; bounded recent retention |
| Governance feedback | keep open findings; resolve/fold learnings; do not retain redundant resolved noise forever |
| Release Audit | frozen by candidate/release identity |
| Temporary/generated report | delete when purpose is complete |

## Bounded retention

Recommended defaults when a project enables `.governance/` observability:

- standard mode: no routine raw execution-log accumulation;
- evaluation mode: keep the latest 50 execution audits unless the user configures another bound;
- when the bound is exceeded, summarize older useful findings into an archive/period summary, then
  remove superseded raw execution records;
- never delete legal/compliance/audit evidence that the project is required to retain.

`scripts/validate_reports.py` can enforce configured retention and handoff structure.

## Principle

**Do not leave project technical debt, and do not manufacture governance technical debt while proving
that you did not.**
