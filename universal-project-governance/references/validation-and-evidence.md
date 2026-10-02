# Validation and Evidence

Load this reference for broad completion claims, deletion, migrations, compatibility assertions,
generated/data changes, or any high-impact change.

## Proof-carrying change

Treat a completed change as a set of claims plus evidence, not just an edited diff.

Typical claim → evidence mappings:

| Claim | Suitable evidence |
|---|---|
| New behavior works | focused test, runtime check, build/render, reproducible procedure |
| Old path is gone | reference/dependency search plus affected tests/build |
| Safe to delete | consumer/dependency/retention analysis plus validation |
| Docs are current | path/name/command checks and targeted doc review |
| Migration complete | source/target/cutover checks, no unintended dual path, contract tests |
| Compatible | explicit compatibility tests/contract evidence, not assumption |
| Generated output current | regeneration from canonical source and diff/check |
| Data state valid | schema/data-quality/integrity checks appropriate to domain |

A passing unit-test suite does not prove documentation, migration, data retention, or handoff quality.
Validate each claim with evidence suited to that claim.

## Proportional validation ladder

Use the smallest ladder that can establish closure:

1. syntax/structural/static checks;
2. focused tests or deterministic checks;
3. contract/schema/interface checks;
4. build/render/compile;
5. data/generated consistency checks;
6. integration/runtime/end-to-end checks when relevant;
7. docs/examples/link/path checks;
8. final diff/review for unintended changes.

Do not run expensive unrelated suites merely for ceremony. Expand when risk or coupling justifies it.

## Evidence ledger

For non-trivial changes, keep enough evidence in the completion report or project record to answer:

- what was checked;
- what command/procedure was actually used;
- what result was observed;
- what surface remains unverified.

Never report a check you did not run.

## Pre-existing failures

Only label a failure "pre-existing" if evidence distinguishes it from the requested change (baseline,
VCS history, reproducible unchanged branch, prior CI, etc.). Otherwise report it as an observed failure
without assigning origin.

## High-churn and heuristics

Heuristics such as high file churn, large file size, many TODOs, or unusual dependency counts are
investigation signals, not proof of fragility, debt, or poor design. Verify before turning a heuristic
into a project fact.

## Validation limitations

If a required environment/service/credential is unavailable, state exactly which claim remains
unverified and what evidence would close it. Do not broaden uncertainty beyond the missing surface.
