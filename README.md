# 通用项目治理 | Universal Project Governance

Current candidate: **3.0.0-rc.6 — Structural Integration & Qualification Hardening**

Universal Project Governance is a model-agnostic Agent Skill for maintained-project engineering governance.

RC6 makes two structural changes:

1. **Non-trivial work defaults to structural integration.** Tiny low-risk edits may remain local; larger work must modify the responsible canonical layer instead of stacking shims, duplicate branches, one-off flags, or detached fixes.
2. **Qualification evidence is now exposure-aware and matrix-complete.** Stable qualification cannot pass from a few pairs, unbalanced subgroups, trigger-inflated safety denominators, invalid attention controls, incomplete handoff criteria, or unmeasured governance artifact overhead.

## Runtime architecture

```text
governance-src/                canonical governance semantics
        ↓ compiler/
universal-project-governance/  generated installable Skill
        ↓ real Agent work
observable project outcome
        ↓
qualification/                 repository-only causal qualification
```

The installed Skill remains bounded. Qualification complexity does not ship with it.

## Structural change mode

The compiled planner now returns:

- `local` — truly local low-risk edits.
- `structural` — medium/high-risk work or intrinsically structural operations such as refactor, migration, dependency, generated-source, architecture, security, data, and governance upgrades.

`STRUCTURAL_INTEGRATION` is a canonical policy, not a prompt convention. It requires the Agent to identify the responsible canonical layer, integrate the change there, remove superseded patch paths when safe, and leave one coherent post-change structure.

## RC6 qualification gates

Stable evidence is non-compensatory and evaluated in this order:

1. locked matrix coverage;
2. evaluator validity;
3. attention-control validity;
4. class-specific critical-safety exposure;
5. core-task non-inferiority;
6. governance uplift;
7. handoff recovery **and** degradation reduction;
8. trigger precision/recall;
9. token/time/tool/artifact efficiency;
10. subgroup generalization.

Release qualification uses **locked evidence only**. Development checkpoints cannot promote Stable.

## Sampling

Formal behavioral qualification requires at least:

- 12 distinct locked behavioral scenarios;
- 8 complete A0/A1/A2 repetitions per scenario × Agent-family cell;
- at least 2 Agent families;
- at least 2 project profiles;
- 6 locked handoff scenarios with 8 paired present/ablated repetitions per scenario × Agent-family cell;
- 100+ trigger cases.

Five repetitions remain a development checkpoint, not a Stable threshold.

## Safety denominator

Critical failures use explicit exposure populations. Trigger and mutation trials never increase destructive-behavior safety denominators.

Each trial carries `safety_exposures`; each critical-failure class receives its own observed-failure count and zero-event confidence bound.

## Current evidence status

RC6 engineering and qualification infrastructure are being validated. No real Agent qualification result is claimed yet. `qualification/results/` is created only by real immutable evidence rounds.

Stable remains blocked until a locked qualification round is **PASS** under the final RC6 qualification fingerprint.

## Maintainer validation

```bash
python compiler/compile_governance.py --check
python tools/governance_lint.py .
python tools/validate_qualification.py .
python tools/qualification_freeze.py . --check
python tools/validate_repository.py .
python -m unittest discover -s tests -v
```

License: Apache-2.0.
