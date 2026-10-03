# Active Design Decisions

## Structural integration is the default for non-trivial work

Tiny local low-risk corrections may remain local. Medium/high-risk work and intrinsically structural operations activate `STRUCTURAL_INTEGRATION`.

The rule exists to prevent repeated local fixes from becoming parallel architecture, hidden compatibility layers, duplicated truth, and growing cleanup debt.

## Structural integration is canonical, not advisory prose

The policy lives in `governance-src/model/governance-model.json`; the compiler emits it into the runtime and the planner reports `change_mode`.

Do not reimplement this rule in docs, adapters, or qualification code.

## Qualification is a separate plane

Qualification code never ships in the Skill. Runtime governance stays bounded while evaluation sophistication can grow independently.

## Release evidence uses locked trials only

Development results are diagnostic. Five repetitions are a checkpoint; Stable cannot pass before 8 complete locked repetitions per scenario × Agent-family cell.

## Primary behavioral matrix must be complete

A release matrix requires A0, A1, and A2 for each paired replication. Every participating Agent family must meet the full locked scenario/repetition minimum; a single token appearance from a second family never satisfies generalization.

## Critical safety uses class-specific exposure populations

Each trial declares the critical-failure classes it can genuinely expose. Safety confidence is calculated per class from those exposures only.

Trigger and mutation trials are excluded from normal treatment safety denominators. Handoff ablation trials are not counted as normal A2 safety exposure.

## Attention control is a validity gate

A1 must be measured against A2 using `governance_context_tokens`. If the control is not within the preregistered ratio, A2>A1 governance uplift is not interpretable and cannot support release.

## Handoff has two independent success criteria

Handoff must improve recovery success and reduce degradation of already-correct checkpoint state. Passing one does not compensate for failing the other.

## Governance artifact overhead is a release criterion

Completed behavioral tasks may not proliferate persistent `.governance` files beyond the locked threshold. Report lifecycle is therefore measured, not merely documented.

## Generalization requires exposure and no severe reversal

Each Agent family and project profile must meet minimum complete-pair exposure. Subgroups may vary, but a severe reversal in task success or governance effect blocks qualification.

## Qualification fingerprint binds the full evidence pipeline

The fingerprint covers protocol, fixtures, evaluators, mutation definitions, adapters, runners, and analyzer. A frozen-surface change requires a new fingerprint and result round.

## Current tree contains current truth

Historical prerelease audits, old version-specific test names, superseded protocol files, and redundant prompt-only eval assets belong in VCS history, not the current working tree.
