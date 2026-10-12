---
name: universal-project-governance
description: Govern maintained-project changes with task-bounded integration, proportional cleanup, evidence, factual chronology, debt control, and recoverable handoffs across project types and tool-using hosts. Use when modifying maintained project state; exclude read-only Q&A and unrelated one-off artifacts.
license: Apache-2.0
compatibility: Core kernel needs no runtime. Optional deterministic planner/state/integrity helpers use Python 3.8+.
metadata:
  version: "3.0.0-rc.19"
  standard: "agentskills.io"
  maturity: "release-candidate"
  architecture: "compiled-governance"
  interoperability: "capability-negotiated"
---

# Universal Project Governance

## Activation

At first modification, resolve the installed Skill. With filesystem/Python run `scripts/project_tool.py ensure <project-root>` for idempotent in-place adoption of UPG-owned state only. Preserve binding-listed infrastructure and existing settings/ledger; uninstall explicitly. New bindings default field reporting off; owner opt-in: `scripts/project_tool.py install <project-root> --field-test-reporting`. Without helpers, use host/project state, disclose binding/report gaps, never fabricate files or block unrelated authorized work for tooling.

Before mutation, inventory available/unavailable filesystem/VCS/search/test/build/browser/app capabilities. Assume no vendor/model/interface/tool class; claim only observed validation.

Adopt legacy projects in place without restructuring/migration: use artifacts as evidence, locate smallest canonical truth, preserve contracts; unknown history/intent stays unknown.

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

Local low-risk edits use the hot path and proportional evidence; no architecture work for isolated corrections. Non-trivial work follows STRUCTURAL_INTEGRATION: remove superseded shims/branches/compatibility paths/detached fixes in scope; no unrelated redesign, API/contract change, migration, or refactor.

Bound task context; batch known source, consumer, contract, evidence and state reads. Apply related source edits together. Derive records from verified actual-byte edit receipts and current reads of unchanged content. Re-read for missing/stale evidence, failed checks, later edits or required project inspection. Run required checks on the final state of their scope; batch independent checks and applicable status. Reuse content only with matching source/tool/context identities and validated cached bytes. Finish with successful required checks, applicable verified receipts and evidence for acceptance and all governance obligations; preserve task quality.

Use verified Python 3.8+ for helpers; on Windows resolve `py -3` or its executable path, never assume `python3` works. Substitute that interpreter below. Compile typed context:

```bash
python scripts/plan_governance.py --project-root /path/to/project --context /path/to/task-context.json
```

The planner validates context schema and binding/reporting health. Follow change mode, scope guard, rule closure, evidence, report level and handoff; no unrelated policy. Unknown optional profiles use universal task/risk rules; exclude no projects.

Without helpers, match `policy-index.json` operation/domains/signals plus `requires` closure.

Assess observable scope/reversibility/security/data impact/external consumers/migration/contract change/unknowns/handoff need. Confidence is not evidence; file/line counts are secondary.

## Evidence and reports

Field reporting is explicit and temporary: one bounded opted-in ledger, no permanent general report per task.

- `none`: final response/VCS evidence.
- `change-note`: compact persistent note if needed.
- `engineering`: `.governance/execution/latest.json`.
- `audit`: frozen release/audit record.

For non-trivial/cross-session work, use a stable workflow ID and minimal `scripts/project_tool.py begin <project-root> --input <workflow.json>` checkpoint when available. Start facts are immutable; update only observed `after`, result/validation revisions and sourced occurrence time. Keep unknowns explicit; Git committer time dates the commit, never work start. Reuse evidence without another history database.

Schema-first state is canonical; Markdown is rendered. Use `scripts/state_tool.py` to validate/render/compact/export.

When writable, keep one current handoff for unfinished work or agent/session transitions. One validation source records run ID, scope/denominator, tested state, result and pending retest. Never overlap counts or equate focused passes with full regression. Check references via `scripts/state_tool.py validate <state.json> --project-root <project-root>`.

After interruption/stale/conflicting state, rebuild scoped truth, entry/dependencies, changes, evidence, UPG state and unresolved artifacts before mutation. Optional read-only `scripts/state_tool.py recover <root> --scope <file>` (repeat scope; explicit `--handoff`/registered `--git-binary`) feeds deltas/carried refs to current handoff. Separate static/dynamic evidence and hypotheses: hashes prove fixity, never validity/truth. Missing intent/partial coverage stay unknown; repeated no progress means switch method or bounded blocker. Act minimally without private chat memory/reasoning.

Order by causal parents/revisions and persistent sequence; `recorded_at` is observation time. Preserve previous change, validate tested state, reconcile stale handoffs with current truth.

At tracked non-trivial boundaries, use `scripts/project_tool.py finish <project-root> --input <report.json>` when available, with the same ID and observed `change`. Stage pins never complete unfinished work: keep `partial`/`blocked` and ID active. Reporting on appends exactly one report; off keeps bounded latest/previous, no ledger. Preserve start facts and stage history: identical retries are idempotent, conflicts fail, one immutable workflow/status receipt. Bound scopes and metadata/evidence; exclude source bodies/secrets/private reasoning. Export/verify before epoch rotation; never reset sequence. Recheck binding; unavailable helpers leave verification gaps, never backfilled historical success.

Installation/receipts/matching behavior/test counts do not prove historical loading or causal benefit. Optional host activation receipts: missing stays unknown. Evaluate matched baseline/attention-control/UPG tasks prospectively with actual token/time/tool costs and cross-agent handoffs.

## Integrity

Never hand-edit generated runtime in ordinary work.

```bash
python scripts/validate_integrity.py .
```

Failed integrity suspends runtime authority. Authorized evolution requires external canonical source, compilation, complexity/static checks, tests, install validation and a new audit candidate.

## Completion

Complete only with applicable behavior/cleanup/truth/evidence/continuity/integrity/binding/active field reporting. State blockers; local review cannot prove project-wide debt clearance.

Uninstall project UPG state before the Skill using the repository CLI; fallback: `scripts/project_tool.py remove <project-root> --yes`, then host Skills CLI removal.

Respect project truth/specialized Skills; reuse canonical structures without parallel documents for filenames.

Bound context: one canonical definition per semantic rule; complexity stays in compiler.
