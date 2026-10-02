# Governance Source

This directory is the **only canonical source** for RC4 governance semantics.

- `model/governance-model.json` defines hot-path invariants, risk dimensions, policy rules, dependencies, evidence contracts, and complexity budgets.
- `profiles/*.json` only activate existing policy IDs; profiles never redefine rules.
- `schemas/*.json` define typed task, plan, handoff, execution, feedback, and audit contracts.
- `templates/SKILL.template.md` is presentation only; semantic rule text comes from the model.
- `runtime-scripts/` contains canonical helper source copied into the generated installable Skill.

Never edit `universal-project-governance/` by hand. Use the compiler and validate generated-runtime drift in CI.
