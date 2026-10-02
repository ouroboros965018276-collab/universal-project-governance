# Migrations and Dependencies

Load this reference for migrations, schema/API changes, compatibility paths, dependency upgrades,
runtime changes, or staged cutovers.

## Migration state machine

A migration must have an explicit lifecycle:

1. **Source** — verified old state.
2. **Target** — intended canonical new state.
3. **Bridge** — compatibility/dual-write/adaptor stage only when necessary.
4. **Cutover** — observable condition that makes the target canonical.
5. **Cleanup** — removal condition for source/bridge residue.
6. **Closed** — validation proves only intended permanent paths remain.

A migration is not closed merely because the new path exists.

For every active bridge, document whether it is temporary or permanent. Temporary bridges require a
removal condition; permanent compatibility requires a rationale and ownership boundary.

## Dependency hygiene

When adding/upgrading/removing dependencies, check:

- is it actually required?
- does an existing dependency already solve the problem adequately?
- does the project accidentally rely on a transitive dependency?
- are manifests and lockfiles synchronized?
- does the change alter runtime, build, security, license, or deployment assumptions?
- did an old dependency become redundant?

Do not upgrade unrelated dependencies solely to chase newest versions unless explicitly in scope or
required for correctness/security/compatibility.

## Contract changes

For API/schema/event/config changes, identify:

- producers and consumers;
- versioning/compatibility promise;
- defaults and failure behavior;
- migration order;
- rollback constraints;
- data transformation/retention impact;
- validation proving old/new interoperability or cutover.

## Dual-path danger

Parallel old/new paths are allowed only when the migration design requires them. Record the cutover and
cleanup trigger. After cutover, remove the old path and its flags/tests/docs unless an explicit
compatibility contract keeps it alive.

## Rollback

Do not promise rollback when data/schema transformations make it unsafe. State actual rollback
constraints and preserve only the artifacts genuinely needed for recovery.
