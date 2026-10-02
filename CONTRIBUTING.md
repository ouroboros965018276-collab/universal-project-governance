# Contributing

Contributions should improve governance capability without linearly increasing runtime cognitive load.

## Change canonical source, not runtime

1. Modify `governance-src/model/`, profiles, schemas, template, or runtime-script source.
2. Add/update plan cases and unit tests for observable behavior.
3. Regenerate the installable runtime:
   ```bash
   python compiler/compile_governance.py --write --confirm-generated-runtime-update
   ```
4. Run compiler drift, governance lint, repository validation, tests, and package build.
5. Update current-state/decision/changelog/audit surfaces when the change is meaningful.

Never hand-edit `universal-project-governance/`.

## Policy additions

Before adding a policy, prove it is not a restatement of an existing stable rule ID. Prefer extending dependency/activation relationships over creating synonymous rules.

New policies need:

- stable ID;
- finite triggers;
- severity;
- evidence contract;
- applicable domains;
- dependency/conflict relationships;
- eval tags and tests.

## Complexity

A feature that violates the complexity budget must be redesigned, consolidated, or accompanied by an explicit evidence-backed budget decision. Do not convert a hard gate into a warning merely to land a feature.
