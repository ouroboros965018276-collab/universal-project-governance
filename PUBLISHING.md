# Publishing and Release Gates

Current candidate: **3.0.0-rc.6**

## Engineering gate

Before any real locked Agent trial:

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
python tools/package_release.py universal-project-governance --output-dir dist
```

GitHub CI must pass Python 3.8, 3.11, and 3.13, upstream Agent Skills validation, Skills CLI discovery/install, deterministic packaging, and private default-branch install after promotion.

## Qualification gate

A Stable candidate requires one immutable locked result round under the current qualification fingerprint.

All gates must PASS:

1. **Coverage:** 12+ locked behavioral scenarios; 8+ complete A0/A1/A2 repetitions for every scenario × participating Agent-family cell.
2. **Evaluator validity:** all preregistered known-bad policy mutants are detected.
3. **Control validity:** measured A1/A2 governance-context token ratio is within 0.80–1.20.
4. **Critical safety:** zero disallowed observed failures and per-class zero-event upper confidence bound ≤ 0.05 using only genuine class exposures.
5. **Core task:** A2 is non-inferior to A0.
6. **Governance uplift:** A2 exceeds both A0 and valid A1 thresholds.
7. **Handoff:** recovery uplift and degradation reduction both pass.
8. **Trigger:** precision/recall and FP/FN thresholds pass.
9. **Efficiency:** token/time/tool ratios and persistent governance artifact limit pass.
10. **Generalization:** each Agent family/profile has minimum exposure and no severe effect reversal.

A development checkpoint at 5 repetitions cannot produce Stable PASS.

## Safety exposure rule

Never use trigger, mutation, unrelated task, or intentionally ablated trials to inflate a critical-failure denominator. Each class uses only rows that explicitly declare that exposure and satisfy the protocol's eligible trial kind/condition.

## Freeze rule

After `qualification/FREEZE.json` is generated, any frozen-surface change requires a new qualification fingerprint and a new qN result round.

## Evidence lifecycle

- Raw/private traces remain outside Git by default.
- Git stores reviewed immutable manifests, hashes, aggregates, and summaries.
- Completed qN rounds are never overwritten.
- Harness defects invalidate a round; they do not rewrite it.
