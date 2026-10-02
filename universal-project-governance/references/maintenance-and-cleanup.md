# Maintenance and Cleanup

Load this reference for refactors, feature replacement, deletion, structural work, upgrades, or any
change with meaningful residue risk.

## Objective

A change is not clean if the new path works while the superseded path, docs, config, data, tests, or
compatibility scaffolding remain ambiguously active.

## Affected-neighborhood sweep

Inspect the smallest coherent neighborhood that can contain residue:

- direct implementation and callers/consumers;
- imports/includes/references;
- config keys, flags, environment examples, manifests and lockfiles;
- tests, fixtures, mocks, snapshots and generated artifacts;
- docs, examples, diagrams, commands and paths;
- schemas, migrations, data transforms and caches;
- deployment/CI/automation references;
- assets and templates.

Search for the old symbol/path/name and for the replacement. A rename is incomplete while canonical
surfaces still use the old identity without an explicit compatibility reason.

## Cleanup classes

Remove or consolidate, when evidence supports it:

- duplicate implementation or business rules;
- dead/unreachable branches;
- obsolete wrappers/adapters/shims;
- stale feature flags and config keys;
- unused direct dependencies;
- abandoned migration scaffolding;
- temporary debug/logging artifacts;
- stale generated outputs;
- orphaned fixtures/data/assets;
- old docs/examples/comments;
- obsolete TODO/FIXME markers;
- duplicate sources of truth;
- transitional naming left after a rename.

Do not "clean" by moving debt elsewhere, renaming a TODO, hiding code behind a flag, or adding a
comment that merely explains why the mess exists.

## Safe deletion protocol

Before deletion, establish reasonable evidence that the artifact is not required by:

1. runtime/operation;
2. build/generation;
3. tests or validation;
4. migration/rollback;
5. data retention/audit/legal requirements;
6. external consumers/contracts;
7. deployment or automation;
8. an owner-maintained manual workflow.

Evidence may include reference search, dependency graphs, schema relationships, VCS history, build or
test results, runtime configuration, generated-source metadata, ownership rules, or explicit user
intent.

**No reference found is a signal, not proof.** Unknown means preserve and investigate, not delete.

For data deletion, require stronger domain-appropriate retention and integrity evidence.

## Refactoring discipline

Prefer a minimal coherent end state:

- one canonical implementation;
- fewer accidental branches;
- stable public contracts unless change is intentional;
- no speculative abstraction for hypothetical future needs;
- no unrelated stylistic rewrite.

If cleanup exposes a much larger unrelated redesign, stop scope growth. Record the finding in the
project's existing concern/backlog mechanism if it materially affects future work, but do not turn a
small task into an unbounded rewrite.

## Generated artifacts

Identify generator/source before editing generated output. Prefer changing the source and regenerating.
If a generated artifact is intentionally committed, refresh it in the same task and validate that it
matches its source.

## Completion evidence

For non-trivial cleanup, be able to show at least one of:

- search proving old symbol/path removal;
- dependency/manifest diff;
- tests/build proving the canonical path;
- generated-output regeneration;
- VCS diff showing replacement rather than parallel accumulation.
