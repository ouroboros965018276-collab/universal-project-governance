# Chronology and Handoff

Load this reference for meaningful changes, releases, multi-module work, AI/engineer handoff, or when
version control is absent/ambiguous.

## Rolling chronology

For the project and each significantly changed unit, preserve at least:

### Last change
- when;
- change/commit ID if available;
- scope;
- before state;
- what changed;
- why;
- after state;
- impact;
- validation;
- removed/superseded material.

### Previous change
The immediately preceding meaningful change with the same fields when evidence exists.

When a new meaningful change closes:

1. move current `last` to `previous`;
2. write new `last`;
3. anchor to change completion/commit time, not arbitrary file mtime;
4. let VCS hold deeper history.

For trivial editorial changes that do not alter project semantics, update the project-level chronology
only if the project convention treats them as meaningful; do not churn every module record.

## Time integrity

Prefer a verified VCS commit/tag or an ISO 8601 timestamp with timezone, for example
`2026-10-02T15:05:00+08:00` or `2026-10-02T07:05:00Z`.

Never invent exact time. If exact time is unavailable but required, mark it `UNRESOLVED` until a
trusted clock/source is available. Avoid ambiguous dates such as `10/02/26`.

## Handoff contract

A competent engineer or AI with no hidden chat context should be able to discover:

- project/module purpose;
- current architecture/state;
- canonical sources of truth;
- important contracts and invariants;
- why non-obvious design exists;
- what changed most recently and why;
- what happened immediately before that;
- what must not be broken;
- how to validate a future change;
- active exceptions and removal conditions.

If any of this exists only in conversation, persist the durable fact in the project.

Do not persist private chain-of-thought, speculative reasoning, or platform-internal metadata. Persist
verified decisions, rationale, interfaces, constraints, validation entry points, chronology, and
active exceptions.

## Version-control integration

When VCS exists:

- use commit IDs/tags as durable anchors when available;
- distinguish working-tree state from committed state;
- do not fabricate commit IDs;
- do not rewrite history unless explicitly required and safe;
- use VCS for deep history rather than copying a long changelog into current-state docs.

## Handoff audit

Before completion, ask: could the next agent safely continue from repository/project state alone?
If the answer depends on "what we discussed earlier", continuity is incomplete.
