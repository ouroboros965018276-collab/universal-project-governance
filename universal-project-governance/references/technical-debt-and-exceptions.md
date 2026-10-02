# Technical Debt and Exceptions

Load this reference whenever legacy behavior, temporary code, compatibility shims, unknown ownership,
unresolved defects, or blocked cleanup appear.

## Debt classes

Look for debt in implementation, architecture, dependencies, compatibility, migrations, tests,
documentation, data, configuration, security hardening, observability, performance, naming/concepts,
ownership/handoff, automation, generated-artifact drift, and vendor/tool coupling.

## Default rule

Within the affected scope:

1. Fix debt that is safely fixable as part of the task.
2. Prove a suspected item is not relevant before dismissing it.
3. If an external constraint blocks resolution, create a bounded exception.

Do not use an exception merely to avoid work that is safely required for closure.

## Bounded exception contract

An active exception must record:

- exact debt/constraint;
- why it cannot be resolved now;
- concrete risk/failure mode;
- affected scope;
- mitigation;
- owner if known;
- removal condition;
- review/expiry trigger when applicable;
- evidence supporting the constraint.

"Temporary", "later", "probably fine", and silent TODOs are not governance.

If the user/task requires zero unresolved debt in the task scope, any active exception blocks
completion.

## Unknown vs intent-dependent

Use `[TODO]` only for a factual gap that can in principle be established from more evidence.
Examples: whether a service is still deployed, whether a file is generated, whether a consumer exists.

Use `[ASK USER]` only when the correct answer depends on owner/team intent rather than repository facts.
Examples: which of two active APIs should remain canonical, or whether a compatibility promise is
still required.

Do not turn every ambiguity into a question. Continue when the choice is evidence-resolvable and safe.

## Priority

When debt competes for attention inside the affected scope, prioritize:

1. correctness, security, privacy, or data-integrity risk;
2. ambiguity likely to cause future wrong changes;
3. obsolete competing implementations;
4. stale docs/comments and duplicate sources of truth;
5. brittle coupling and migration residue;
6. unnecessary dependencies/automation;
7. cosmetic inconsistency.

## Closure language

Never claim the entire project is debt-free from a local change. The strongest default claim is:

> No known unmanaged debt was introduced or left in the affected scope.

Only use it when your evidence supports it.
