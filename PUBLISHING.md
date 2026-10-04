# Publishing and Test-Freeze Gates

Current candidate: **3.0.0-rc.11**

## Engineering gate before real-Agent testing

All must pass:

```bash
python compiler/compile_governance.py --check
python tools/governance_lint.py .
python tools/validate_qualification.py .
python tools/qualification_freeze.py . --check
python tools/validate_repository.py .
python tools/validate_skill_bundle.py universal-project-governance
python universal-project-governance/scripts/validate_integrity.py universal-project-governance
python tools/security_audit.py .
python -m unittest discover -s tests -v
```

CI must also pass Linux Python 3.8/3.11/3.13, Windows Python 3.11/3.13, upstream Agent Skills validation, local lifecycle install/remove, clean Codex-target installation, deterministic packaging, and private default-branch installation after promotion.

## Real-Agent locked gate

One immutable result round under the current qualification fingerprint must satisfy every non-compensatory gate:

Evidence admission comes first: registered round, current frozen identity, schema-valid isolated executions, matched model/adapter/host conditions and retained artifact bytes. Rejected inputs never reach release inference. Analyzer exits 1 for FAIL and 2 for MORE_DATA; neither exit promotes Stable.

1. complete locked scenario/Agent/arm coverage;
2. project deployment integrity and completion reports;
3. evaluator mutation sensitivity;
4. attention-control validity;
5. class-specific critical safety;
6. scope-overreach control with independent `local_guard` and `structural_guard` exposure/confidence bounds;
7. core-task non-inferiority;
8. governance uplift;
9. handoff recovery and degradation reduction;
10. trigger precision/recall;
11. token/time/tool/task-artifact/managed-file efficiency;
12. subgroup generalization under explicit CI semantics.

## Formal inference

Primary CIs use preregistered hierarchical bootstrap over Agent family → scenario → pair/repetition.

Subgroup CI evidence is reported directly. Generalization PASS means the preregistered severe-reversal criterion is established; it does not silently imply significant benefit in every subgroup.

## Field-test evidence

Personal and friend gray testing may export `upg-field-test-reports.json`. These reports are diagnostic field evidence, not substitutes for locked qualification.

Before Stable, the report capability receives an explicit retain/remove decision. The disabled path is already executable: fresh binding creates no ledger and report/export operations are unavailable. Existing non-empty ledgers must be exported and purged before retirement; `remove` refuses to proceed while history remains and never silently discards it.

## Freeze rule

After `qualification/FREEZE.json` is regenerated for the current candidate, no frozen surface changes during a result round. Any such change invalidates the round and requires a new fingerprint.
