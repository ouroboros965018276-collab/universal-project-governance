# Canonical Governance Source

`governance-src/` is the only editable source of runtime governance semantics.

## Why this layer exists

The installable Skill is generated. Keeping one canonical typed source prevents documentation drift, duplicated rules, and hand-edited runtime patches.

## RC6 structural-integration contract

`model/governance-model.json` defines `STRUCTURAL_INTEGRATION` and the activation rule:

- tiny/low-risk local work may remain local;
- medium/high-risk work defaults to structural mode;
- refactor, migration, dependency, generated-source, architecture, security, data, and governance upgrades force structural mode;
- release bookkeeping itself is exempt.

The planner emits `change_mode` so downstream Agents and audits can observe the decision.

## Change safety

A governance semantic change requires:

1. canonical source edit;
2. compiler regeneration;
3. governance lint;
4. runtime integrity;
5. deterministic tests;
6. qualification freeze regeneration;
7. new empirical evidence if the behavioral fingerprint changes.

Do not add a second source of the same rule elsewhere.
