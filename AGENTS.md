# AGENTS.md

## Repository contract

This repository is in RC5 Protocol Freeze.

### Governance behavior is frozen

Governance semantics live under governance-src/. The installable universal-project-governance/ directory is generated.
During RC5 qualification do not add or alter Policy IDs, Hot Path semantics, risk semantics, handoff/report semantics, compiler contract, or runtime capabilities unless the owner explicitly accepts invalidating the freeze.

### Qualification work

Repository-only empirical infrastructure lives under qualification/ and must not ship in the Skill.
Formal locked experiments require fresh isolated workspaces. Do not expose holdout oracles, graders, expected answers, or qualification sources to the Agent under test.
Do not create fake empty result files. Result rounds exist only after real evidence is generated.
Do not request or store private chain-of-thought; keep observable tool/file/test/outcome evidence and usage metadata.

### Required deterministic checks

    python compiler/compile_governance.py --check
    python tools/governance_lint.py .
    python tools/validate_freeze_delta.py
    python tools/validate_qualification.py .
    python tools/validate_repository.py .
    python -m unittest discover -s tests -v

After qualification/FREEZE.json exists, also run tools/qualification_freeze.py --check.
If real qualification finds a core governance defect, report failure honestly. Version-number preference never overrides evidence.
