# Documentation and Current Truth

Load this reference when behavior, architecture, structure, names, interfaces, setup, operation,
constraints, or module meaning changes.

## Truth-surface principle

Normative documentation describes the current project. Deep history belongs in VCS or a dedicated
history mechanism, not mixed into current instructions.

When reality changes, update the canonical description in the same task and remove/rewrite
contradictory material. Do not append "new behavior" below stale "old behavior" and leave both active.

## Significant-unit semantics

For each significant module/component/artifact, make these discoverable somewhere canonical:

- **Function** — what it does.
- **Purpose** — why the project needs it.
- **Rationale** — why this approach exists when non-obvious.
- **Scope** — where it is used and where it is not.
- **Inputs / outputs** — important contracts.
- **Dependencies / consumers** — important relationships.
- **Invariants** — conditions that must remain true.
- **Change safety** — what is local vs coordinated.
- **Status** — active, transitional, compatibility-only, generated, external, etc.
- **Last / previous meaningful change** — when useful for continuity.

Centralize these semantics in an existing architecture/module map rather than duplicating them through
source comments.

## Comments and labels

Comments should explain non-obvious intent, invariants, tradeoffs, hazards, or constraints. Do not
narrate self-evident syntax.

Useful durable labels, where project conventions support them:

- `PURPOSE:` why this exists;
- `INVARIANT:` what must remain true;
- `CONTRACT:` externally relied-upon behavior;
- `COMPAT:` compatibility reason plus removal/permanence condition;
- `GENERATED:` source and regeneration method;
- `EXTERNAL:` externally owned constraint;
- `EXCEPTION:` bounded unresolved constraint reference;
- `DEPRECATED:` only with a real migration/removal path.

Do not add modification timestamps to every source file. Use VCS and centralized governance state to
avoid timestamp drift.

## One-source-of-truth rule

For each volatile fact, identify one independently editable canonical source. If tooling requires
copies, mark them generated/derived and document the generator.

Before creating `PROJECT_STATE.md`, `MODULE_MAP.md`, `DECISIONS.md`, or `EXCEPTIONS.md`, search for an
existing equivalent. Integrate rather than create a second governance system.

## Anti-drift checks

Check for:

- old filenames/paths after rename;
- removed commands or flags;
- stale architecture diagrams/screenshots;
- examples that no longer execute;
- contradictory setup paths;
- unsupported feature claims;
- placeholders presented as implemented behavior;
- validation claims not actually obtained;
- duplicated volatile facts.

When docs and implementation conflict, investigate intended current state. Do not automatically assume
either is correct.

## Bootstrap semantics

If governance docs are absent, the templates in `assets/` are defaults. Preserve their semantics, but
adapt filenames and structure to existing project conventions. Do not create documentation merely to
satisfy a filename checklist.
