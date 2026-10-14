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

Before the first edit, resolve the installed Skill and run `scripts/project_tool.py ensure <root>` when available (idempotent, UPG-owned state only). Adopt in place without restructuring or migration merely to install: preserve project contracts, binding-listed infrastructure, settings and ledgers. Existing artifacts are evidence; never invent their history or intent. Without helpers, use host/project state, disclose binding/report gaps, and neither fabricate files nor block unrelated authorized work.

Observe available and unavailable host capabilities before mutation; assume no vendor, model, interface or tool class. Claim only observed validation.

1. **ONE_CURRENT_TRUTH** — Reuse one canonical source of truth; update or remove obsolete normative state instead of creating parallel truth.
2. **PROPORTIONAL_CLEANUP** — Every project change gets cleanup proportional to its affected neighborhood; remove replaced, duplicate, temporary, or stale residue when safe.
3. **EVIDENCE_BEFORE_CLAIM** — Deletion, migration, compatibility, validation, and debt/completion claims require evidence appropriate to the claim.
4. **NO_FABRICATION** — Unknown facts stay unknown; never invent history, timestamps, ownership, rationale, validation, deployment state, or consumer intent.
5. **NO_UNMANAGED_DEBT** — Safely fixable in-scope debt is fixed; externally blocked debt becomes a bounded exception with risk and removal/review condition.
6. **VALIDATE_AFFECTED** — Run the smallest sufficient checks that establish the affected behavior, cleanup, truth, and contract claims.
7. **HANDOFF_IF_UNFINISHED** — If work crosses an agent/session boundary or remains unfinished, persist current handoff state when possible; if interruption prevented handoff, the next actor reconstructs from project truth and observable work state without inventing intent.
8. **STRUCTURAL_INTEGRATION** — Except for truly local low-risk edits, integrate at the smallest responsible canonical layer and remove superseded patch paths; structural mode never authorizes unrelated redesign, API change, migration, or cleanup outside task scope.

**decision_relevance** — Keep only information current readers need for project use/maintenance/validation/takeover. Use the user's language; fit wording/format to task/readers. Explain operations in delivery; README only if project understanding needs it. No mechanical style rules or extra model polishing calls.

**complete_change** — Complete the scoped task at its existing correct responsible layer. Preserve contracts, safety/error handling; resolve affected consumers/tests and obsolete paths. Minimize needless work, not lines/diff/deletion volume. Priority: user intent; correctness/safety/truth; contracts/structure; maintainability/readability; cost.

**evidence_fidelity** — Make concrete, evidence-matched claims. Preserve technical identifiers, numbers, references, negation and unknowns when rewriting/shortening.

**task_scoped_reading** — Locate task modules/symbols/document anchors via indexes or bounded search. Indexes route reads, never prove complete dependencies. Trace implementation/contracts/consumers/tests; widen for stale/conflicting indexes, dynamic dependencies or coverage gaps. Use existing fact recovery for interrupted/stale/contradictory state. Read budgets never prove completion.

Keep this Skill loaded: a plan projects its task-specific obligations and is not standalone. With a verified Python 3.8+ executable, run `scripts/plan_governance.py --project-root <root> --context <context.json>`. On Windows resolve `py -3` or its executable; never assume `python3` works. The planner checks context, binding and reporting health. Follow its mode, scope guard, closures, evidence, report and handoff. Without helpers, match `policy-index.json` operations/domains/signals, dependency closure and risk/report rules alongside this Skill. Unknown optional profiles retain universal rules; no project is excluded. Assess observable risk, never confidence as evidence.

Batch known reads/edits and independent checks. Derive records and dependent after-state hashes from verified actual-byte edit receipts or still-current unchanged-content reads; do not reread solely for a verified current hash. Reread for missing/stale evidence, failed checks, later edits or required inspection. Reuse cached bytes only with matching source/tool/context identities.

## State when needed

Apply the plan's operational guidance once. Without helpers, select policy-index.json blocks when policy_ids intersects active rules, report_levels includes the resolved report, or on_field_reporting and existing reporting are both true. Non-trivial, tracked or cross-session work must apply tracked_state even if context missed its trigger; correct that context. Use existing payload schemas. Reconstruct interrupted/conflicting state before mutation without private chat memory or invented intent.

Field reporting defaults off; enable it only by explicit temporary owner opt-in through project_tool install --field-test-reporting. Preserve existing settings. Keep one bounded ledger when enabled, never permanent general per-task reports. Report levels apply either way: `none` uses final response/VCS evidence; `change-note` a needed compact persistent note; `engineering` `.governance/execution/latest.json`; `audit` a frozen release/audit record.

## Verify and finish

Complete only after required checks pass on final scoped state, with verified receipts and evidence for all applicable behavior, cleanup, truth, continuity, integrity, binding and active-reporting obligations. State blockers; local review never establishes project-wide debt clearance.

Installation, receipts, matching behavior and tests prove neither historical loading nor causal benefit. Missing optional host activation receipts stay unknown. Prospectively compare matched baseline/attention-control/UPG tasks using actual token/time/tool costs and cross-agent handoffs.

Ordinary work must not edit generated governance runtime. Run `scripts/validate_integrity.py <skill-root>`; failure suspends its authority. Authorized evolution requires external canonical source, a new version/candidate, regeneration, complexity/static checks, tests, installation validation and audit.

Explicitly uninstall project UPG state before the Skill through the repository CLI; fallback: `scripts/project_tool.py remove <root> --yes`, then host Skills CLI removal.

Respect project truth and specialized Skills. Reuse canonical structures, never filename-driven parallel documents. Keep one canonical definition per rule; put complexity in the compiler.
