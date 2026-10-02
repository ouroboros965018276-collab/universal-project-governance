# Version and Authorized Evolution Policy

The canonical installed-Skill version is `metadata.version` in `SKILL.md`.

## PATCH

Use for corrections that do not materially change the behavioral contract, such as:

- typo or broken-link fixes;
- validator bug fixes that restore already-intended behavior;
- non-semantic documentation clarification.

## MINOR

Use for backward-compatible new governance capability, workflow, reference, template, or validation
behavior.

## MAJOR

Use when changing activation semantics, core completion invariants, compatibility expectations, or
other behavior that can make a previously valid project workflow invalid.

## Pre-release candidates

During pre-release development, use `X.Y.Z-rc.N`. Any release-relevant change after a candidate has
been validated creates a new RC identity and requires the applicable gates to rerun.

## Authorized protocol change

Before modifying protected Skill files:

1. the task must explicitly be about upgrading/repairing the Skill;
2. record why the existing behavior is insufficient;
3. classify version impact;
4. update the Skill changelog and behavioral eval coverage;
5. refresh integrity checksums using the explicit upgrade command;
6. rerun structural, security, integrity, runtime, install, and behavioral gates appropriate to the change.

Do not let an unrelated project task silently become a Skill-upgrade task.
