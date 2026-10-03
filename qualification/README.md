# Qualification Plane

Purpose: determine whether the frozen Skill causally improves real engineering outcomes enough to justify its cost.

This directory is repository-only and never ships in the installed Skill.

## Protocol v2

`protocol/qualification-v2.json` is the preregistered release contract. `thresholds.json` contains numeric release criteria.

Formal evidence uses locked trials only. Development runs are diagnostic.

## Evidence model

Every formal behavioral/handoff trial records:

- Agent/model/scaffold identity;
- tool and budget profile;
- locked/dev evidence set;
- experimental arm/condition;
- explicit `safety_exposures`;
- observable outcome;
- measured usage;
- persistent governance artifact count;
- behavioral and qualification fingerprints.

Trigger and mutation trials declare no normal critical-safety exposure.

## Analyzer structure

- `analysis/metrics.py`: statistical primitives.
- `analysis/coverage.py`: matrix completeness.
- `analysis/gates.py`: one implementation per release criterion.
- `analyze.py`: orchestration only.

This separation exists to prevent release semantics from becoming hidden inside a single conditional-heavy script.

## Sampling

Development minimum: 3 repetitions per cell.  
Checkpoint: 5.  
Locked Stable minimum: 8.  
Borderline progression: 10, then 12 maximum before `MORE_DATA`.

Every participating Agent family must complete the full locked behavioral matrix. Project profiles must meet their minimum complete-pair exposure.

## Critical safety

Safety is class-specific.

For each CF class:

1. select normal locked A2 rows;
2. retain only rows declaring that class in `safety_exposures`;
3. enforce eligible trial kind/condition;
4. count observed failures;
5. compute the zero-event confidence bound from that class's denominator.

No unrelated rows may improve the bound.

## Attention control

A1 is valid only when measured `governance_context_tokens` is within the locked ratio to A2. If control validity fails, A2>A1 uplift is not interpretable.

## Handoff

Formal handoff compares `present` vs `ablated` under controlled checkpoints.

It measures both final recovery success and whether Agent B regressed state that Agent A had already made correct at the checkpoint.

## Results

Real runs create immutable `results/qN/` evidence. This repository intentionally contains no fabricated empty result files.
