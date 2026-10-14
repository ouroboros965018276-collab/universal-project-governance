---
name: universal-project-governance
description: Govern maintained projects; exclude read-only Q&A and unrelated one-offs.
license: Apache-2.0
compatibility: Core needs no runtime; optional helpers need Python 3.8+.
metadata:
  version: "{{VERSION}}"
  maturity: "release-candidate"
---

# Universal Project Governance

## Activate and route

Before the first edit, resolve the installed Skill and run `scripts/project_tool.py ensure <root>` when available (idempotent, UPG-owned state only). Adopt in place without restructuring or migration merely to install: preserve project contracts, binding-listed infrastructure, settings and ledgers. Existing artifacts are evidence; never invent their history or intent. Without helpers, use host/project state, disclose binding/report gaps, and neither fabricate files nor block unrelated authorized work.

Observe available and unavailable host capabilities before mutation; assume no vendor, model, interface or tool class. Claim only observed validation.

{{HOT_PATH}}

{{EXECUTION_GUIDANCE}}

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
