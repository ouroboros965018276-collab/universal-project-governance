# Qualification Plane

Purpose: establish whether the frozen RC7 Skill causally improves real engineering outcomes enough to justify its behavioral and operational cost.

This directory is repository-only.

## Protocol q3

`protocol/qualification-v3.json` preregisters arms, sampling, hierarchical inference, safety exposure, deployment integrity, structural overreach, efficiency, subgroup semantics, and stopping rules.

Development runs are diagnostic. Stable evidence uses locked trials only.

## Hierarchical inference

Formal paired effects use hierarchical bootstrap:

```text
agent_family
  → scenario_id
    → pair_id / repetition
```

This avoids treating all repetitions as simple IID observations.

## Generalization

Every Agent-family and project-profile subgroup reports task/governance CIs.

The gate distinguishes:

- `positive-subgroup-evidence`
- `severe-reversal-ruled-out-only`

Coverage/generalization does not automatically claim statistically significant benefit for every subgroup.

## Structural overreach

Behavioral labs define a scope contract. Locked A2 trials measure unexpected changed files, unrequested API/architecture changes, changed-file count, diff lines, and latency.

The overreach gate is independent from task success.

## Project deployment

A2 behavioral evidence includes project-binding validity and the required completion report. Fixed UPG managed files are counted separately from task governance artifacts.

## Results

Real result rounds appear under `results/qN/` only after execution and are immutable. No fabricated empty result artifacts are permitted.
