# AGENTS.md

Current candidate: **3.0.0-rc.20.8 — Whole-project Contract Reconciliation**.

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

Binding schema v2 records in-place adoption, handoff-or-reconstruct continuity, capability handshake, and whether the project existed before adoption. Never rewrite these paths outside the project-tool lifecycle.

## Completion

For tracked non-trivial work, begin and finish through `project_tool.py`. Each observed partial/blocked boundary uses a stable `checkpoint_id`; identical retries add nothing. Reference existing canonical project state with `current_state` (path/SHA), then check `status`; stale references require reconciliation. `latest_change` means latest completed workflow, not current unfinished progress. Reporting on appends bounded history; off keeps active recovery and latest/previous completion without a ledger. Do not copy source bodies, credentials, secrets, customer/private data, or private chain-of-thought into reports.

Explicit scoped Git enablement bootstraps the project root and verified initial commit when needed. The lifecycle executes Git checkpoints; hosts without it use a configured foreground project-session watcher only when their command waits for the actual session. A session end or owner crash ends its observer subtree; there is no detached start, persistent process, OS startup, or injected host configuration. Unsupported hosts use finite checkpoints/ticks. Configuration, scope, cooldown and recovery are defined in [docs/git-checkpoints.md](docs/git-checkpoints.md); the canonical tracked-state guidance routes to the helper. Check the actual finish result before claiming a commit or clean handoff.

## Continuity

When a transition is planned and unfinished, maintain one factual current handoff if possible.

If the previous actor stopped abruptly before creating one, reconstruct before changing anything: inspect canonical project truth, observable worktree/VCS or equivalent changes, existing validation, UPG state, and unresolved artifacts. Separate facts from hypotheses and never fabricate the missing actor's intent.

This applies across human/AI boundaries, sessions, vendors, and Agent classes.

## Qualification

Formal locked trials use fresh strong-isolation workspaces. Real trial evidence binds Agent/model/scaffold plus adapter configuration/runtime and host-tool identity. Handoff trials bind both source and receiving conditions.

Do not edit a frozen surface after a real result round begins.

Exposed regression fixtures cannot become an independent holdout again. Keep bounded artifact tasks separate from real tool execution, cross-Agent handoff, and formal qualification evidence. Requested model names, reported completed-turn usage, and provider-internal attempt coverage must retain their observed limits.

Evidence overrides desired release outcomes.

## Task context and maintained content

Apply the canonical execution_guidance from governance-src/model/governance-model.json through the generated Skill and planner. MODULE_MAP.md is this repository's source/contract/consumer/test routing entry. Keep governance semantics in that canonical source; this file does not define another writing, change or reading policy.
