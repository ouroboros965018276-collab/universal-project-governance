# Qualification Plane

Purpose: establish whether the frozen RC8 Skill causally improves maintained-project outcomes enough to justify its behavioral and operational cost.

This directory is repository-only and never ships as Agent runtime.

## Protocol q3

`protocol/qualification-v3.json` preregisters arms, sampling, hierarchical inference, safety exposure, deployment integrity, structural overreach, execution identity, efficiency, subgroup semantics, and stopping rules.

Development runs are diagnostic. Stable evidence uses locked trials only.

## Hierarchical inference

Formal paired effects use hierarchical bootstrap:

```text
agent_family
  → scenario_id
    → pair_id / repetition
```

RC8 requires at least three locked Agent families. Resampling 4,000 times cannot manufacture additional independent top-level clusters, so cross-family generalization is reported separately and is intentionally narrower than within-family precision.

## Reproducible execution identity

Locked behavioral evidence records:

- Agent family;
- model ID;
- scaffold version;
- adapter configuration SHA-256;
- adapter implementation/runtime SHA-256;
- host-tool name/version;
- tool profile;
- budget profile.

Cross-Agent handoff trials additionally record the source-side Agent family, adapter-config identity, and host-tool identity. Evidence produced under materially different adapter/host conditions cannot silently collapse into the same paired cell.

## Cross-Agent continuity

Handoff trials may use a different continuation adapter from the source adapter. This allows the qualification plane to test continuation across different Agent classes/vendors/hosts rather than only a second invocation of the same scaffold.

The runtime also supports abrupt no-handoff recovery through reconstruction. Qualification fixtures distinguish successful explicit handoff from ablated handoff and preserve observable task state so recovery/degradation can be measured without private reasoning.

## Generalization

Every Agent-family and project-profile subgroup reports task/governance CIs.

The gate distinguishes:

- `positive-subgroup-evidence`
- `severe-reversal-ruled-out-only`

Coverage/generalization does not automatically claim statistically significant benefit for every subgroup.

## Structural overreach

Behavioral labs define a scope contract. Locked A2 trials measure unexpected changed files, unrequested API/architecture changes, changed-file count, diff lines, and latency.

The overreach gate is independent from task success and has two non-pooled populations: `local_guard` detects unnecessary structuralization of local tasks; `structural_guard` detects structural work escaping its smallest justified canonical layer.

## Project deployment

A2 behavioral evidence includes RC8 binding-v2 validity and completion-report cardinality. A completed modifying workflow passes deployment integration only when exactly one report was recorded.

Fixed UPG managed files are counted separately from task governance artifacts.

## Trigger coverage

Trigger fixtures cover English and Chinese modifying/read-only contrasts across software, data, infrastructure, ML/AI, automation, docs, design systems, research, content, product, and operations objects. The trigger rule remains semantic: maintained-project state changes activate governance; read-only explanation/review does not.

## Results

Real result rounds appear under `results/qN/` only after execution and are immutable. No fabricated empty result artifacts are permitted.
