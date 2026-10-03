# AGENTS.md

Current candidate: **3.0.0-rc.7 — Real-Agent Test Freeze**.

## Change mode

For a truly local low-risk correction, keep work local.

For non-trivial work, integrate into the **smallest responsible canonical layer**. Structural mode does not authorize unrelated redesign, API/contract changes, architectural migration, or opportunistic refactoring.

Remove superseded in-scope patch paths when safe. Do not create wrappers, fallbacks, duplicate configs, parallel truths, or compatibility layers as permanent substitutes for proper integration.

## Generated runtime

Governance semantics live in `governance-src/`. `universal-project-governance/` is generated and must not be hand-edited.

## Project binding

On the first modifying activation, ensure the project binding using the installed runtime. `.governance/upg.json` is always UPG-managed; `.governance/field-reports.json` is managed only while `field_test_reporting=true`. Managed UPG state is not garbage.

Do not remove or rewrite them outside the explicit project-tool lifecycle.

## RC7 completion report

While field-test reporting is enabled, every completed modifying workflow records exactly one field report before completion is claimed. If reporting is disabled in a future runtime, do not recreate the ledger or emit reports.

Reports contain bounded metadata/evidence summaries only. Never copy source bodies, credentials, secrets, or private chain-of-thought into them.

## Qualification

Formal locked trials use fresh strong-isolation workspaces. Never expose holdout oracles, other-arm outcomes, or hidden graders to the tested Agent.

Do not edit any frozen surface once a real result round starts.

## Handoff

If work stops unfinished, persist factual continuation state and validation entry points. Do not rely on chat memory.

Evidence overrides desired release outcomes.
