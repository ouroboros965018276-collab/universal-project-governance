# Contributing

Contributions are welcome when they improve governance quality without turning the Skill into a vendor-specific prompt dump or a second documentation system.

## Rules

- Keep this as **one Skill**.
- `universal-project-governance/SKILL.md` is the canonical behavior contract.
- Detailed policy belongs in a focused `references/` file only when the main router can state exactly when to load it.
- Runtime helpers must be deterministic, network-free, conservative around secrets, and read-only by default.
- Do not weaken safe deletion, evidence-before-claim, current-truth, chronology, interoperability, or closure gates to make tests pass.
- Observable behavior changes require corresponding `evals/` updates.
- Repository state changes must update current project governance docs when affected.

## Local checks

```bash
python tools/validate_skill_bundle.py universal-project-governance
python tools/validate_repository.py .
python tools/security_audit.py .
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
python universal-project-governance/scripts/validate_project_governance.py .
```

Before release promotion, follow `PUBLISHING.md` and rerun the full GitHub Actions pipeline from a clean commit.
