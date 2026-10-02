# Publishing and Release Gates

## RC5 engineering gate

Before qualification or candidate promotion run:

    python compiler/compile_governance.py --check
    python tools/governance_lint.py .
    python tools/validate_freeze_delta.py
    python tools/validate_qualification.py .
    python tools/validate_repository.py .
    python tools/validate_skill_bundle.py universal-project-governance
    python universal-project-governance/scripts/validate_integrity.py universal-project-governance
    python -m unittest discover -s tests -v
    python tools/package_release.py universal-project-governance --output-dir dist

Final RC5 freeze additionally requires:

    python tools/qualification_freeze.py . --check

GitHub CI must continue to pass Python 3.8 / 3.11 / 3.13, upstream Agent Skills validation, Skills CLI discovery/install, security audit, deterministic package construction, and default-branch private install after promotion.

## RC4→RC5 behavioral freeze

RC5 may not add runtime governance semantics. The normalized behavioral fingerprint must equal the frozen RC4 baseline despite the rc.5 version identity. A changed fingerprint invalidates RC5 qualification evidence.

## Qualification prerequisites

- protocol status locked;
- qualification/FREEZE.json matches frozen surfaces;
- evaluator sensitivity can detect declared known-bad policy mutants;
- locked holdouts run only inside strong isolated workspaces;
- endpoints, critical failures, thresholds, budgets, randomization and stopping rules are preregistered;
- graders are calibrated before release evidence is interpreted.

## Stable qualification gate

2.0.0 Stable requires a real immutable qualification round whose summary is PASS under the frozen qualification fingerprint.

Required non-compensatory gates: evaluator validity; no disqualifying critical safety regression; core-task non-inferiority; positive governance uplift versus no-Skill and attention-control; positive cross-agent handoff recovery; trigger precision/recall within threshold; overhead within budget; cross-agent/project-profile generalization.

Zero observed critical failures must be reported with sample size and a confidence upper bound, never as proof of zero risk.

## Evidence storage

Large/private raw traces remain in controlled CI/artifact storage by default. Git keeps immutable manifests, content hashes, generated aggregates, and summaries. Completed qN rounds are never overwritten; a harness defect invalidates the round and creates qN+1.

## Promotion

If RC5 passes and the behavioral fingerprint remains unchanged, release metadata may promote to 2.0.0 Stable without invalidating behavioral evidence. If qualification fails, Stable is blocked; thresholds are not moved after seeing results.
