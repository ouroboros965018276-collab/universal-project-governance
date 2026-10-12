---
name: universal-project-governance
description: Govern maintained-project changes across project types and hosts with task-bounded integration, proportional cleanup, evidence, factual chronology, debt control, recoverable handoffs. Exclude read-only Q&A/unrelated one-offs.
license: Apache-2.0
compatibility: Core needs no runtime. Optional deterministic planner/state/integrity helpers use Python 3.8+.
metadata:
  version: "3.0.0-rc.19"
  standard: "agentskills.io"
  maturity: "release-candidate"
  architecture: "compiled-governance"
  interoperability: "capability-negotiated"
---

# Universal Project Governance

## Activation

First edit: resolve installed Skill; with filesystem/Python, `scripts/project_tool.py ensure <root>` (idempotent, in-place, UPG-owned state only). Keep binding-listed infrastructure and existing settings/ledger; uninstall explicitly. New bindings: field reporting off; owner opt-in: `scripts/project_tool.py install <root> --field-test-reporting`. No helpers: use host/project state, disclose binding/report gaps; never fabricate files or block unrelated authorized work.

Before mutation inventory available/unavailable filesystem/VCS/search/test/build/browser/app capabilities. Assume no vendor/model/interface/tool class; claim only observed validation.

Legacy adoption: in place, no restructuring/migration. Artifacts are evidence; find smallest canonical truth, keep contracts; unknown history/intent stays unknown.

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

Low-risk local corrections: hot path/proportional evidence, no architecture work. Non-trivial: STRUCTURAL_INTEGRATION; remove in-scope superseded shims/branches/compatibility paths/detached fixes. No unrelated redesign/API/contract change/migration/refactor.

Bound context; batch known source/consumer/contract/evidence/state reads and related edits. Derive records from verified actual-byte edit receipts/current unchanged-content reads. Re-read for missing/stale evidence, failed checks, later edits or required project inspection. Run required checks on final scoped state; batch independent checks/applicable status. Reuse only with matching source/tool/context identities and validated cached bytes. Finish with successful required checks, applicable verified receipts and evidence for acceptance/all governance obligations; preserve task quality.

Helpers: verified Python 3.8+; Windows: resolve `py -3` or its executable, never assume `python3`. Substitute below. Typed context: `python scripts/plan_governance.py --project-root <root> --context <context.json>`.

Planner validates context schema/binding/reporting health; follow change mode/scope guard/rule closure/evidence/report level/handoff, no unrelated policy. Unknown optional profiles: universal task/risk rules, exclude no projects. No helpers: match `policy-index.json` operation/domains/signals plus `requires` closure.

Assess observable scope/reversibility/security/data impact/external consumers/migration/contract change/unknowns/handoff need. Confidence is not evidence; file/line counts secondary.

## Evidence and reports

Field reporting: explicit temporary owner opt-in, one bounded ledger; no permanent general per-task report.

Task report levels (regardless of field reporting): `none` final response/VCS evidence; `change-note` needed compact persistent note; `engineering` `.governance/execution/latest.json`; `audit` frozen release/audit record.

Non-trivial/cross-session: stable workflow ID, minimal `scripts/project_tool.py begin <root> --input <workflow.json>` checkpoint when available. Start facts immutable; update only observed `after`, result/validation revisions, sourced occurrence time. Unknowns explicit; Git committer time dates commit, never work start. Reuse evidence, no extra history database.

Schema-first state is canonical, Markdown rendered. `scripts/state_tool.py`: validate/render/compact/export.

When writable: one current handoff for unfinished work/agent/session transitions. One validation source: run ID/scope/denominator/tested state/result/pending retest. Never overlap counts/equate focused passes with full regression. Check refs: `scripts/state_tool.py validate <state.json> --project-root <root>`.

After interruption/stale/conflict, rebuild scoped truth/entry/dependencies/changes/evidence/UPG state/unresolved artifacts before mutation. Optional read-only `scripts/state_tool.py recover <root> --scope <file>` (repeat scope; explicit `--handoff`/registered `--git-binary`): carry deltas/refs into current handoff. Separate static/dynamic evidence from hypotheses; hashes prove fixity, never validity/truth. Missing intent/partial coverage stay unknown; repeated no progress: change method/bounded blocker. Act minimally without private chat memory/reasoning.

Order by causal parents/revisions, persistent sequence; `recorded_at` is observation time. Preserve prior change, validate tested state, reconcile stale handoffs with current truth.

Tracked non-trivial boundaries: `scripts/project_tool.py finish <root> --input <report.json>` when available; same workflow ID/observed `change`. Stage pins keep unfinished work `partial`/`blocked`, ID active. Field reporting on: append exactly one; off: bounded latest/previous, no ledger. Keep start facts/stage history; identical retries idempotent, conflicts fail, one immutable workflow/status receipt. Bound scopes/metadata/evidence; no source bodies/secrets/private reasoning. Export/verify before epoch rotation; never reset sequence. Recheck binding; helper gaps stay verification gaps, no historical-success backfill.

Installation/receipts/matching behavior/test counts do not establish historical loading or causal benefit. Optional host activation receipts: missing unknown. Prospectively compare matched baseline/attention-control/UPG tasks: actual token/time/tool costs, cross-agent handoffs.

## Integrity

Never hand-edit generated runtime in ordinary work. `python scripts/validate_integrity.py .`: failure suspends runtime authority. Authorized evolution requires external canonical source/compilation/complexity/static checks/tests/install validation/new audit candidate.

## Completion

Complete only with applicable behavior/cleanup/truth/evidence/continuity/integrity/binding/active field reporting. State blockers; local review does not establish project-wide debt clearance.

Uninstall project UPG state before the Skill via repository CLI; fallback: `scripts/project_tool.py remove <root> --yes`, then host Skills CLI removal.

Respect project truth/specialized Skills; reuse canonical structures, no filename-driven parallel documents.

Bound context: one canonical definition per semantic rule; complexity in compiler.
