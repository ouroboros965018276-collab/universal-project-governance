# Canonical Governance Source

`governance-src/` is the only editable source of distributed governance semantics.

## RC7 responsibilities

The canonical model defines:

- bounded Hot Path and policy graph;
- risk-adaptive planning;
- task-bounded structural integration;
- the two-file project binding;
- temporary RC7 field-test reporting;
- runtime complexity budgets.

Runtime helpers and schemas are compiled from this directory.

## Structural scope rule

Structural work changes the smallest responsible canonical layer. It must not reinterpret “structural” as permission to widen task scope.

## Project binding

RC7 uses exactly two managed project paths. Field reports use one bounded rolling ledger instead of per-task files.

The reporting switch is canonical so the capability can be intentionally retained or structurally removed before Stable.

## Change safety

Any semantic change requires regeneration, lint, runtime integrity, deterministic tests, qualification-freeze regeneration, and new empirical evidence if a result round has already started.

Validation uses the explicit schema subset implemented by state_tool.py (types/unions, object properties, required, const, enum, array bounds/uniqueness, string bounds/patterns/RFC3339, numeric bounds). New schema keywords require implementation and negative tests.
