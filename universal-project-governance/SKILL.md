---
name: universal-project-governance
description: Govern maintained-project changes with task-bounded integration, proportional cleanup, evidence, factual chronology, debt control, and recoverable handoffs across project types and tool-using hosts. Use when modifying maintained project state; exclude read-only Q&A and unrelated one-off artifacts.
license: Apache-2.0
compatibility: Core kernel needs no runtime. Optional deterministic planner/state/integrity helpers use Python 3.8+.
metadata:
  version: "3.0.0-rc.14"
  standard: "agentskills.io"
  maturity: "release-candidate"
  architecture: "compiled-governance"
  interoperability: "capability-negotiated"
---

# Universal Project Governance

A compiled governance runtime. The canonical governance model lives outside the installed Skill; this directory is generated and integrity-checked.

## Activation

Use for any maintained-project state change. Do not activate for read-only explanation/review/research that makes no project change.

At the first modifying activation, resolve this installed Skill and run `scripts/project_tool.py ensure <project-root>` when filesystem and Python are available. New project bindings keep empirical field-test reporting disabled by default; an owner can explicitly opt in with `scripts/project_tool.py install <project-root> --field-test-reporting`. Existing bindings preserve their current setting and ledger. Otherwise apply the same rules through existing host/project state and explicitly report unavailable binding/report verification; do not fabricate files or block unrelated authorized work merely to install tooling. This idempotently adopts both new and pre-existing projects in place: it adds only UPG-owned state and does not restructure legacy project content. Files listed by that binding are managed UPG infrastructure: preserve them during ordinary cleanup and remove them only through the explicit uninstall path.

Before changing project state, perform a capability handshake from observable host facts: identify available filesystem/VCS/search/test/build/browser/app tools and unavailable capabilities. Govern the task with what exists; never assume a specific vendor, model, interface, or tool class, and never fabricate a validation that the current host cannot perform.

For an existing project that predates UPG, treat current project artifacts as evidence, not automatically as correct design. Locate the smallest existing canonical sources of truth, preserve working contracts, mark unknown history/intent as unknown, and make governance effective on the current task immediately. Do not demand a project-wide migration merely to adopt UPG.

## Hot path

1. **ONE_CURRENT_TRUTH** — Reuse one canonical source of truth; update or remove obsolete normative state instead of creating parallel truth.
2. **PROPORTIONAL_CLEANUP** — Every project change gets cleanup proportional to its affected neighborhood; remove replaced, duplicate, temporary, or stale residue when safe.
3. **EVIDENCE_BEFORE_CLAIM** — Deletion, migration, compatibility, validation, and debt/completion claims require evidence appropriate to the claim.
4. **NO_FABRICATION** — Unknown facts stay unknown; never invent history, timestamps, ownership, rationale, validation, deployment state, or consumer intent.
5. **NO_UNMANAGED_DEBT** — Safely fixable in-scope debt is fixed; externally blocked debt becomes a bounded exception with risk and removal/review condition.
6. **VALIDATE_AFFECTED** — Run the smallest sufficient checks that establish the affected behavior, cleanup, truth, and contract claims.
7. **HANDOFF_IF_UNFINISHED** — If work crosses an agent/session boundary or remains unfinished, persist current handoff state when possible; if interruption prevented handoff, the next actor reconstructs from project truth and observable work state without inventing intent.
8. **STRUCTURAL_INTEGRATION** — Except for truly local low-risk edits, integrate at the smallest responsible canonical layer and remove superseded patch paths; structural mode never authorizes unrelated redesign, API change, migration, or cleanup outside task scope.

## Execution

For a truly local low-risk edit, apply the hot path directly and keep evidence proportional. Do not manufacture architecture work for a typo or equivalent isolated correction.

For non-trivial work, prefer structural integration at the smallest responsible canonical layer over patch stacking. Structural mode is task-bounded: it does **not** authorize unrelated redesign, API/contract changes, migrations, or opportunistic refactors. Remove superseded shims, duplicate branches, temporary compatibility paths, and detached fixes only inside the justified task surface.

Create a typed task context and compile the task-specific plan:

```bash
python3 scripts/plan_governance.py --project-root /path/to/project --context /path/to/task-context.json
```

The planner validates the full task-context schema and reads the healthy project binding so its field-report obligation reflects the actual project setting. Unknown optional profiles fall back to universal task/risk rules; profiles never exclude a project. The plan returns the change mode (`local` or `structural`), an explicit scope guard, active rule closure, required evidence, report level, and whether handoff state is required. Execute that plan; do not load unrelated governance policy.

If helpers are unavailable, read `policy-index.json` and apply only rules matching the task operation/domains/signals plus their `requires` closure.

## Risk context

Use observable facts, not model confidence. Risk dimensions are scope, reversibility, security, data impact, external consumers, migration, contract change, unknowns, and handoff need. File/line counts are secondary signals only.

## Evidence and reports

Do not create a permanent general-purpose governance report for every task. Field-test reporting is an explicit, temporary evaluation mode, disabled by default for new projects; opted-in bindings maintain one bounded ledger.

- `none`: concise final response/VCS evidence is enough.
- `change-note`: compact persistent note only if the project needs it.
- `engineering`: maintain `.governance/execution/latest.json`.
- `audit`: use a frozen release/audit record.

For non-trivial or cross-session work, record a stable workflow ID and the minimal active checkpoint with `scripts/project_tool.py begin <project-root> --input <workflow.json>` when available. Use the report schema change contract for function, before/after, rationale/source, base/result/validated revision, known occurrence time/source and parent event; unknown values stay explicit. Reuse existing project evidence, not a new history database.

Schema-first governance state is canonical. Markdown is a rendered view, not a second editable truth. Use `scripts/state_tool.py` to validate/render/compact/export governance state.

A current handoff is required when work is unfinished or deliberately crosses an agent/session boundary, when the actor can write one. Keep at most one current handoff.

Abrupt interruption is a supported continuity mode, not an exceptional assumption. If a prior actor disappeared before writing a handoff, the next actor must reconstruct before modifying: inspect canonical project truth, VCS/worktree or equivalent observable changes, existing validation/evidence, current UPG state, and unresolved artifacts. Separate observed facts from inferred possibilities, mark prior intent that cannot be recovered as unknown, then continue from the smallest safe next action. Never require private chat memory or chain-of-thought for recovery.

Use causal parent/revision references and persistent sequence for order. Tool `recorded_at` is observation time, never invented work/commit time. Preserve the previous change and tie validation to the actually tested state; a stale handoff is evidence to reconcile, not authority to overwrite current truth.

For tracked non-trivial work, use `scripts/project_tool.py finish <project-root> --input <report.json>` to record completion. It shares one reconciliation path across reporting modes: with `field_test_reporting=true` it appends exactly one report; otherwise it advances bounded latest/previous state without creating a ledger. Partial or blocked work remains active for recovery. Include `workflow_id` and `change` metadata. Identical retries are idempotent; conflicting retries fail. Export and verify evidence before explicit epoch rotation; sequence never resets, and task IDs are unique within the declared retention epoch. The ledger stores metadata/evidence summaries only, never source contents, secrets, or private chain-of-thought. With reporting disabled, do not create a field ledger or report merely to satisfy the ordinary governance-note level.

## Integrity

This installed runtime is generated. During ordinary project work do not edit it.

```bash
python3 scripts/validate_integrity.py .
```

If integrity fails, stop treating the modified runtime as authoritative. Authorized Skill evolution happens in canonical governance source, followed by compilation, complexity/static checks, tests, install validation, and a new audit candidate.

## Completion

A modifying task is complete only when applicable behavior, cleanup, truth, evidence, continuity, integrity, project-binding, and active field-test-report obligations are satisfied. State unresolved blockers precisely; never expand a local review into a project-wide debt-free claim.

For uninstall, remove project-managed UPG state before removing the Skill. The repository convenience CLI performs both steps automatically; the runtime-safe fallback is `scripts/project_tool.py remove <project-root> --yes` followed by the host Skills CLI removal.

## Interoperability

Respect existing project sources of truth and specialized Skills. Governance semantics may live in existing canonical project structures; do not create parallel documentation merely to match a filename.

## Final rule

Governance capability may grow, but runtime cognitive load must remain bounded. One semantic rule has one canonical definition; complexity belongs in the compiler, not in agent context.
