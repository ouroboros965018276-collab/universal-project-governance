# AGENTS.md

Current candidate: **3.0.0-rc.14 — Runtime Integrity and Diagnostic Hardening**.

## First modifying activation

Resolve the installed Skill and ensure the project binding before modifying maintained project state.

Adopt existing projects in place. Do not restructure legacy content merely to install UPG. Treat existing artifacts as evidence, locate current canonical truth, preserve observed contracts, and keep unknown history or intent explicitly unknown.

## Capability handshake

Use observable host capabilities rather than vendor assumptions. Identify what filesystem, VCS, search, test/build, browser/application, or other tools are actually available. Do not invent validation or state that cannot be observed.

## Change mode

Keep genuinely local low-risk corrections local.

For non-trivial work, integrate at the **smallest responsible canonical layer**. Structural mode does not authorize unrelated redesign, API/contract changes, architectural migration, or opportunistic refactoring.

Remove superseded in-scope patch paths when safe. Do not create wrappers, fallbacks, duplicate configs, parallel truths, or compatibility layers as permanent substitutes for proper integration.

## Generated runtime

Governance semantics live in `governance-src/`. `universal-project-governance/` is generated and must not be hand-edited.

## Project binding

`.governance/upg.json` is always UPG-managed. `.governance/field-reports.json` is managed only while field-test reporting is enabled. Managed UPG state is infrastructure, not cleanup residue.

New project bindings default field-test reporting off. Qualification A2 workspaces must explicitly opt in; preserve any existing enabled state and ledger during routine adoption.

RC9 binding v2 records in-place adoption, handoff-or-reconstruct continuity, capability handshake, and whether the project existed before adoption. Never rewrite these paths outside the project-tool lifecycle.

## Completion

For tracked non-trivial work, begin and finish through `project_tool.py`. The `finish` command records one completion path in both reporting modes: reporting on appends exactly one bounded field report; reporting off advances the existing latest/previous checkpoints without creating a ledger. Partial or blocked work remains active for recovery. Do not copy source bodies, credentials, secrets, customer/private data, or private chain-of-thought into reports.

## Continuity

When a transition is planned and unfinished, maintain one factual current handoff if possible.

If the previous actor stopped abruptly before creating one, reconstruct before changing anything: inspect canonical project truth, observable worktree/VCS or equivalent changes, existing validation, UPG state, and unresolved artifacts. Separate facts from hypotheses and never fabricate the missing actor's intent.

This applies across human/AI boundaries, sessions, vendors, and Agent classes.

## Qualification

Formal locked trials use fresh strong-isolation workspaces. Real trial evidence binds Agent/model/scaffold plus adapter configuration/runtime and host-tool identity. Handoff trials bind both source and receiving conditions.

Do not edit a frozen surface after a real result round begins.

Evidence overrides desired release outcomes.
