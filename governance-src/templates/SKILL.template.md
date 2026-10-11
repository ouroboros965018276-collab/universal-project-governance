---
name: universal-project-governance
description: Govern maintained-project changes with task-bounded integration, proportional cleanup, evidence, factual chronology, debt control, and recoverable handoffs across project types and tool-using hosts. Use when modifying maintained project state; exclude read-only Q&A and unrelated one-off artifacts.
license: Apache-2.0
compatibility: Core kernel needs no runtime. Optional deterministic planner/state/integrity helpers use Python 3.8+.
metadata:
  version: "{{VERSION}}"
  standard: "agentskills.io"
  maturity: "release-candidate"
  architecture: "compiled-governance"
  interoperability: "capability-negotiated"
---

# Universal Project Governance

## Activation

At first modification, resolve the installed Skill; with filesystem/Python run `scripts/project_tool.py ensure <project-root>`: idempotent in-place adoption adding only UPG-owned state. Preserve binding-listed infrastructure during cleanup; uninstall explicitly. New bindings default empirical field reporting off; owner opt-in: `scripts/project_tool.py install <project-root> --field-test-reporting`. Preserve existing settings/ledger. Without helpers, govern through host/project state; disclose binding/report gaps. Never fabricate files or block unrelated authorized work for tooling.

Before mutation, inventory available/unavailable filesystem/VCS/search/test/build/browser/app capabilities. Assume no vendor/model/interface/tool class; claim only possible, observed validation.

Adopt legacy projects now without restructuring/migration: artifacts are evidence; locate smallest canonical truth, preserve contracts; unknown history/intent stays unknown.

## Hot path

{{HOT_PATH}}

## Execution

Local low-risk edits use the hot path and proportional evidence; no architecture work for isolated corrections.

Integrate non-trivial work at the smallest responsible canonical layer; remove superseded shims/branches/compatibility paths/detached fixes in scope. No unrelated redesign, API/contract change, migration, or refactor.

Use a verified Python 3.8+ interpreter for helpers; on Windows resolve `py -3` or its full executable path rather than assuming `python3` works. Substitute that interpreter for `python` below. Compile typed context:

```bash
python scripts/plan_governance.py --project-root /path/to/project --context /path/to/task-context.json
```

The planner validates full context schema and healthy binding/reporting. Follow change mode, scope guard, rule closure, evidence, report level, and handoff; no unrelated policy. Unknown optional profiles use universal task/risk rules; exclude no projects.

Without helpers, match `policy-index.json` operation/domains/signals plus `requires` closure.

Use observable scope/reversibility/security/data impact/external consumers/migration/contract change/unknowns/handoff need. Model confidence is not evidence; file/line counts are secondary.

## Evidence and reports

Field reporting is temporary, explicit, with one bounded opted-in ledger; no permanent general report per task.

- `none`: final response/VCS evidence.
- `change-note`: compact persistent note if needed.
- `engineering`: `.governance/execution/latest.json`.
- `audit`: frozen release/audit record.

Non-trivial/cross-session work: stable workflow ID, minimal checkpoint via `scripts/project_tool.py begin <project-root> --input <workflow.json>` when available. Start facts stay immutable; update observed `after`, result/validation revisions, sourced occurrence time only. Unknowns stay explicit; Git committer time dates its commit, never work start. Reuse evidence, not another history database.

Schema-first state is canonical; Markdown is rendered. Use `scripts/state_tool.py` to validate/render/compact/export.

When writable, keep one current handoff for unfinished work/planned agent/session transitions. One validation fact source: run ID, scope/denominator, tested state, result, pending retest. No overlapping counts or focused-pass/full-regression conflation. Check optional references: `state_tool.py validate/render --project-root <project-root>`.

After interruption without handoff, reconstruct before mutation: canonical truth, VCS/worktree/equivalent changes, validation/evidence, UPG state, unresolved artifacts. Separate facts/inferences; unrecoverable intent stays unknown. Take the smallest safe action without private chat memory/reasoning.

Order by causal parents/revisions and persistent sequence; `recorded_at` is observation time. Preserve previous change; validate tested state. Reconcile stale handoffs against current truth.

At tracked non-trivial boundaries, use `scripts/project_tool.py finish <project-root> --input <report.json>` when available: same workflow ID, observed `change`. Stage pins leave unfinished work `partial`/`blocked`, ID active. Reporting on: exactly one appended report; off: bounded latest/previous, no ledger. Start facts immutable; identical retries idempotent, conflicts fail; one immutable workflow/status receipt. Bound scopes; retain stage history. Export/verify before epoch rotation; sequence never resets. Bounded metadata/evidence only, no source bodies/secrets/private reasoning. Recheck binding; unavailable helpers leave verification gaps, never backfilled historical success.

Installation/receipts/matching behavior/test counts prove neither historical loading nor causal benefit. Use optional host activation receipts; missing stays unknown. Evaluate matched baseline/attention-control/UPG tasks prospectively with actual token/time/tool costs and cross-agent handoffs.

## Integrity

Never hand-edit generated runtime in ordinary work.

```bash
python scripts/validate_integrity.py .
```

Failed integrity suspends runtime authority. Authorized evolution: external canonical source, compilation, complexity/static checks, tests, install validation, new audit candidate.

## Completion

Completion requires applicable behavior/cleanup/truth/evidence/continuity/integrity/binding/active field reporting. State blockers; local review proves no project-wide debt clearance.

Uninstall project UPG state before the Skill. Repository CLI handles both; fallback: `scripts/project_tool.py remove <project-root> --yes`, then host Skills CLI removal.

Respect project truth/specialized Skills; reuse canonical governance structures, no parallel documents for filenames.

Bound context: one canonical definition per semantic rule; complexity stays in compiler.
