---
name: universal-project-governance
description: Govern maintained projects; exclude read-only Q&A and unrelated one-offs.
license: Apache-2.0
compatibility: Core needs no runtime; optional helpers need Python 3.8+.
metadata:
  version: "3.0.0-rc.20.5"
  maturity: "release-candidate"
---

# Universal Project Governance

## Activate and route

First edit: resolve installed Skill; `scripts/project_tool.py ensure <root>` if available (idempotent; UPG-owned state only). Adopt in place; preserve contracts, binding-listed infrastructure, settings/ledgers; no installation-driven restructuring/migration. Before mutation inventory available/unavailable host capabilities; no vendor/model/tool assumptions, only observed validation claims. No helpers: project/host state, disclose binding/report gaps; never fabricate files or block unrelated authorized work.

1. **ONE_CURRENT_TRUTH** — Reuse one canonical source of truth; update or remove obsolete normative state instead of creating parallel truth.
2. **PROPORTIONAL_CLEANUP** — Every project change gets cleanup proportional to its affected neighborhood; remove replaced, duplicate, temporary, or stale residue when safe.
3. **EVIDENCE_BEFORE_CLAIM** — Deletion, migration, compatibility, validation, and debt/completion claims require evidence appropriate to the claim.
4. **NO_FABRICATION** — Unknown facts stay unknown; never invent history, timestamps, ownership, rationale, validation, deployment state, or consumer intent.
5. **NO_UNMANAGED_DEBT** — Safely fixable in-scope debt is fixed; externally blocked debt becomes a bounded exception with risk and removal/review condition.
6. **VALIDATE_AFFECTED** — Run the smallest sufficient checks that establish the affected behavior, cleanup, truth, and contract claims.
7. **HANDOFF_IF_UNFINISHED** — If work crosses an agent/session boundary or remains unfinished, persist current handoff state when possible; if interruption prevented handoff, the next actor reconstructs from project truth and observable work state without inventing intent.
8. **STRUCTURAL_INTEGRATION** — Except for truly local low-risk edits, integrate at the smallest responsible canonical layer and remove superseded patch paths; structural mode never authorizes unrelated redesign, API change, migration, or cleanup outside task scope.

**decision_relevance** — Use the user's language. Keep project content useful for current use, maintenance, validation or takeover. Give the needed outcome, evidence and limits once. Fit technical detail and reasons to need; omit process recitals, rigid style rules and extra model polishing.

**complete_change** — Keep contracts/safety/error handling; resolve affected consumers/tests and obsolete paths. Use current bytes/revisions and the tool's edit semantics; a fragment cannot replace a whole file. Change edge/error returns/exceptions only for the authorized goal. Minimize needless work, not diff size; reserve final validation/handoff budget and check every explicit task obligation before finishing. Priority: user intent; correctness/safety/truth; contracts/structure; maintainability/readability; cost.

**evidence_fidelity** — Observe validation on the final affected state before claiming completion. Later edits invalidate affected evidence: rerun those checks before completion, or report pending checks and keep work unfinished. Preserve identifiers, input domains, numbers, references, negation and evidence limits when shortening; distinguish planned, failed and unknown checks from observed results.

**task_scoped_reading** — Honor required reads; discover existing paths/anchors via indexes or bounded search before batching. Writable paths may be planned additions; listings/links alone are not read obligations. Trace implementations/contracts/consumers/tests; expand for dependencies, failures, stale/conflicting evidence or coverage gaps. Defer unrelated material. Recover interrupted/stale/contradictory state from project evidence. Indexes/labels/read budgets never prove coverage; unknowns stay unknown.

Keep Skill loaded; plans are not standalone. Verified Python 3.8+: `scripts/plan_governance.py --project-root <root> --context <context.json>` checks context/binding/report health; obey its mode/scope guard/closures/evidence/report/handoff obligations. Windows: resolve `py -3` or its executable, never assume `python3`. No helpers: `policy-index.json` operations/domains/signals, dependencies and risk/report rules. Unknown optional profiles retain universal rules; observable risk, not confidence; missing facts unassessed.

Batch independent checks. After-state hashes: verified actual-byte receipts or still-current reads. Reread stale/missing evidence, later edits, failed checks or required inspection; cached bytes require matching source/tool/context identities.

## State when needed

Apply selected operational blocks once. No helpers: select when policy_ids intersects active rules OR report_levels contains resolved report OR (on_field_reporting AND existing field reporting). Also select tracked_state for non-trivial/tracked/cross-session work; correct missed triggers.

Preserve reporting settings: field reporting defaults off; explicit temporary owner opt-in only (`project_tool install --field-test-reporting`). On: one bounded ledger, no permanent per-task reports. Both modes: `none` final/VCS evidence; `change-note` needed compact note; `engineering` `.governance/execution/latest.json`; `audit` frozen record.

## Verify and finish

Finish only when selected obligations, integrity, binding and active reporting hold. State blockers; local review cannot establish project-wide debt clearance.

Installation/receipts/matching behavior/tests prove neither historical loading nor causal benefit; missing activation receipts stay unknown. Prospectively measure matched baseline/attention-control/UPG actual token/time/tool costs and cross-agent handoffs.

Ordinary work must not edit installed Skill files or canonical governance source. Run `scripts/validate_integrity.py <skill-root>`; failure suspends authority. Explicitly authorized evolution needs external canonical source, new version/candidate, regeneration, complexity/static checks, tests, installation validation and audit.

Explicit uninstall: project state first via repository CLI or `scripts/project_tool.py remove <root> --yes`, then host Skills CLI. Respect project truth/specialized Skills; reuse canonical structures, no filename-driven parallel documents. One definition per rule; compiler absorbs complexity.
