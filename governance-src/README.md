# Canonical Governance Source

`governance-src/` is the only editable source of distributed governance semantics.

## Canonical responsibilities

The canonical model defines:

- bounded Hot Path and policy graph;
- risk-adaptive planning;
- task-bounded structural integration;
- the two-file project binding;
- opt-in temporary field-test reporting;
- schema-validated task contexts and shared completion reconciliation;
- runtime complexity budgets.

Runtime helpers and schemas are compiled from this directory.

`runtime-scripts/project_tool.py` owns the workflow lifecycle. Its `finish` command updates bounded completion state when reporting is disabled and delegates to the same exactly-once ledger path when reporting is enabled. `runtime-scripts/plan_governance.py` validates the complete task-context schema before compiling a plan; unknown optional profile labels remain universal fallbacks.

## Structural scope rule

Structural work changes the smallest responsible canonical layer. It must not reinterpret “structural” as permission to widen task scope.

## Project binding

Project bindings manage at most two paths. New projects default to only `.governance/upg.json`; opting into field-test reporting adds one bounded rolling ledger instead of per-task files. Existing opted-in ledgers are preserved during adoption and upgrades.

The default and per-project switch are canonical. Qualification A2 runners explicitly opt into reporting; ordinary projects are not forced to collect research data.

## Change safety

Any semantic change requires regeneration, lint, runtime integrity, deterministic tests, qualification-freeze regeneration, and new empirical evidence if a result round has already started.

Validation uses the explicit schema subset implemented by state_tool.py (types/unions, object properties, required, const, enum, array bounds/uniqueness, string bounds/patterns/RFC3339, numeric bounds). New schema keywords require implementation and negative tests.
