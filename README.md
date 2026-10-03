# 通用项目治理 | Universal Project Governance

Current candidate: **3.0.0-rc.7 — Real-Agent Test Freeze**

Universal Project Governance is a model-agnostic Agent Skill for maintained-project engineering governance.

RC7 is the final engineering freeze before real-Agent qualification. It preserves the compiled, bounded Skill architecture while tightening inference, preventing structural overreach, automating project installation/removal, and collecting bounded gray-test evidence.

## Architecture

```text
governance-src/                canonical governance semantics
        ↓ compiler/
universal-project-governance/  generated installable Skill
        ↓
project binding                .governance/upg.json
field-test ledger              .governance/field-reports.json
        ↓
real Agent work
        ↓
qualification/                 repository-only causal qualification
```

Qualification code never ships as Agent runtime.

## Structural integration is task-bounded

The planner returns `change_mode` and `scope_guard`.

- `local / local-only`: truly local low-risk work.
- `structural / task-bounded-responsible-layer`: non-trivial work changes the smallest responsible canonical layer and removes superseded patch paths, but does not authorize unrelated redesign, API/contract changes, architectural migration, or opportunistic refactoring.

RC7 measures structural overreach independently from task correctness.

## Foolproof project lifecycle

Repository checkout:

```bash
python upg.py install --project /path/to/project --agent codex
python upg.py status --project /path/to/project
python upg.py export --project /path/to/project --output upg-field-test-reports.json
python upg.py remove --project /path/to/project --agent codex --yes
```

The install command installs the Skill through `skills@1.7.0`, validates the installed copy, and initializes the project binding.

If the Skill is installed directly through a host Skills CLI rather than `upg.py`, the first modifying activation runs the idempotent project-binding `ensure` operation.

Only two persistent files are owned by UPG during RC7 field testing:

- `.governance/upg.json`
- `.governance/field-reports.json`

They are managed infrastructure, not cleanup residue. Explicit uninstall removes only UPG-owned state and preserves unrelated project-owned governance files.

## Gray-test report

While `field_test_reporting=true`, every completed modifying workflow must append exactly one bounded report record. Reports contain metadata/evidence summaries, not source contents or private chain-of-thought.

The ledger is fixed-cardinality: one file, at most 200 reports. Export it and upload the exported JSON for cross-project analysis.

This reporting plane is deliberately isolated behind the canonical `project_binding.field_test_reporting` switch so it can be removed structurally before Stable if empirical testing shows no durable value.

## Qualification v3

Formal primary confidence intervals use hierarchical bootstrap:

```text
Agent family
  → scenario
    → repetition / pair
```

Release gates are non-compensatory:

1. locked matrix coverage;
2. deployment integrity;
3. evaluator validity;
4. attention-control validity;
5. class-specific critical safety;
6. structural-overreach control;
7. core-task non-inferiority;
8. governance uplift;
9. handoff recovery and degradation reduction;
10. trigger precision/recall;
11. efficiency;
12. subgroup generalization.

Generalization distinguishes “severe reversal ruled out” from “positive subgroup evidence”; a coverage PASS is not described as subgroup statistical significance.

## Current evidence status

RC7 source/runtime/qualification engineering validation is complete and the real-Agent test identity is machine-frozen. No real Agent causal result is claimed yet and no `qualification/results/` placeholder exists.

Stable remains blocked until immutable locked real-Agent evidence passes the frozen RC7 protocol.

License: Apache-2.0.
