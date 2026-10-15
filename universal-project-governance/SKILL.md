---
name: universal-project-governance
description: Govern maintained projects; exclude read-only Q&A and unrelated one-offs.
license: Apache-2.0
compatibility: Core needs no runtime; optional helpers need Python 3.8+.
metadata:
  version: "3.0.0-rc.20"
  maturity: "release-candidate"
---

# Universal Project Governance

## Activate and route

Before the first edit, resolve this installed Skill and run `scripts/project_tool.py ensure <root>` if available (idempotent; UPG-owned state only). Adopt in place: preserve contracts, binding-listed infrastructure, settings and ledgers; installation never requires restructuring or migration. Before mutation observe available/unavailable host capabilities; claim only observed validation. Assume no vendor/model/tool class. Without helpers, use project/host state, disclose binding/report gaps, and neither fabricate files nor block unrelated authorized work.

1. **ONE_CURRENT_TRUTH** — Reuse one canonical source of truth; update or remove obsolete normative state instead of creating parallel truth.
2. **PROPORTIONAL_CLEANUP** — Every project change gets cleanup proportional to its affected neighborhood; remove replaced, duplicate, temporary, or stale residue when safe.
3. **EVIDENCE_BEFORE_CLAIM** — Deletion, migration, compatibility, validation, and debt/completion claims require evidence appropriate to the claim.
4. **NO_FABRICATION** — Unknown facts stay unknown; never invent history, timestamps, ownership, rationale, validation, deployment state, or consumer intent.
5. **NO_UNMANAGED_DEBT** — Safely fixable in-scope debt is fixed; externally blocked debt becomes a bounded exception with risk and removal/review condition.
6. **VALIDATE_AFFECTED** — Run the smallest sufficient checks that establish the affected behavior, cleanup, truth, and contract claims.
7. **HANDOFF_IF_UNFINISHED** — If work crosses an agent/session boundary or remains unfinished, persist current handoff state when possible; if interruption prevented handoff, the next actor reconstructs from project truth and observable work state without inventing intent.
8. **STRUCTURAL_INTEGRATION** — Except for truly local low-risk edits, integrate at the smallest responsible canonical layer and remove superseded patch paths; structural mode never authorizes unrelated redesign, API change, migration, or cleanup outside task scope.

**decision_relevance** — Keep only information current readers need for project use/maintenance/validation/takeover. Use the user's language; fit wording/format to task/readers. Deliver relevant outcomes/evidence/gaps once, with needed technical detail and why/when. Omit governance/process recitals; put task-rule explanations in project content only if project understanding needs them. No mechanical style rules or extra model polishing calls.

**complete_change** — Keep contracts/safety/error handling; resolve affected consumers/tests and obsolete paths. Change edge/error returns/exceptions only as required by the authorized goal. Minimize needless work, not diff size. Priority: user intent; correctness/safety/truth; contracts/structure; maintainability/readability; cost.

**evidence_fidelity** — Make concrete, evidence-matched claims. Preserve technical identifiers, numbers, references, negation and unknowns when rewriting/shortening.

**task_scoped_reading** — Honor required reads; select relevant paths/anchors via indexes or bounded search before batching. Listings/links alone are not read obligations. Trace implementations/contracts/consumers/tests; expand for dependencies, failures, stale/conflicting evidence or coverage gaps. Defer unrelated material. Recover interrupted/stale/contradictory state from project evidence. Indexes/labels/read budgets never prove coverage; unknowns stay unknown.

Keep this Skill loaded; a plan is not standalone. With verified Python 3.8+, run `scripts/plan_governance.py --project-root <root> --context <context.json>` for context/binding/report health and task obligations. Windows: resolve `py -3` or its executable, never assume `python3`. Follow mode, scope guard, closures, evidence, report and handoff. Without helpers, resolve `policy-index.json` operations/domains/signals, dependencies and risk/report rules. Unknown optional profiles retain universal rules. Assess observable risk, not confidence.

Batch known relevant reads/edits and independent checks. Reuse verified actual-byte receipts or still-current reads for after-state hashes; reread for stale/missing evidence, later edits, failed checks or required inspection. Cached bytes require matching source/tool/context identities.

## State when needed

Apply each selected operational block once. Without helpers, select index blocks when policy_ids intersects active rules OR report_levels contains the resolved report OR (on_field_reporting AND existing field reporting). Non-trivial, tracked or cross-session work also requires tracked_state; correct missed context triggers. Use existing schemas and reconstruct interrupted/conflicting state from project evidence before mutation.

Preserve reporting settings. Field reporting defaults off; enable only by explicit temporary owner opt-in: `project_tool install --field-test-reporting`. When enabled keep one bounded ledger, no permanent per-task reports. Report levels apply either way: `none` final/VCS evidence; `change-note` a needed compact note; `engineering` `.governance/execution/latest.json`; `audit` a frozen record.

## Verify and finish

Complete only with required checks and verified evidence on final affected behavior, cleanup, truth, continuity, integrity, binding and active reporting. State blockers; local review cannot establish project-wide debt clearance.

Installation, receipts, matching behavior or tests prove neither historical loading nor causal benefit; missing activation receipts stay unknown. Measure matched baseline/attention-control/UPG prospectively with actual token/time/tool costs and cross-agent handoffs.

Ordinary tasks must not edit generated governance runtime. Run `scripts/validate_integrity.py <skill-root>`; failure suspends authority. Authorized evolution needs external canonical source, a new version/candidate, regeneration, complexity/static checks, tests, installation validation and audit.

For explicit removal, uninstall project state before the Skill: repository CLI, or `scripts/project_tool.py remove <root> --yes` then host Skills CLI. Respect project truth and specialized Skills; reuse canonical structures, never filename-driven parallel documents. One definition per rule; compiler absorbs complexity.
