# Interoperability with Other Skills and Project Systems

Load this reference when another Skill, generator, documentation suite, policy engine, or project-local
workflow already owns part of the same surface.

## Ownership-first rule

Before creating or rewriting governance artifacts, identify ownership:

- project-native source of truth;
- generated output and its generator;
- external/tool-managed namespace;
- another Skill's output contract;
- human-owned/manual process.

Do not create a competing editable truth merely because this Skill has a default template.

## Specialized Skill coexistence

When a specialized Skill is active:

- specialized Skill: owns domain procedure/output contract;
- universal-project-governance: owns cleanup, current-state integrity, debt governance, chronology,
  evidence, and handoff around the resulting change.

If the specialized Skill requires an exact output namespace/file set, treat that namespace as reserved.
Do not add governance files inside it unless that Skill explicitly allows it.

Example: a codebase-discovery Skill may own `docs/codebase/` and require exactly seven files. Keep this
Skill's state elsewhere or integrate into existing project docs rather than violating that contract.

## Conflict priority

Use this order:

1. platform/system/safety/legal requirements;
2. explicit current user/task instructions;
3. repository/project-local authoritative instructions;
4. specialized active workflow constraints for their owned surface;
5. this Skill's governance defaults;
6. inferred conventions;
7. style preference.

A lower layer must not silently override a higher layer.

## Semantic integration

The required semantics are:

- current project truth;
- significant-unit purpose/boundaries/invariants;
- last/previous meaningful change;
- validation entry points/evidence;
- active exceptions.

These semantics may live in existing `ARCHITECTURE.md`, ADRs, service catalogs, generated docs,
issue trackers, metadata files, or other canonical structures. Do not duplicate them solely to match
this Skill's filenames.

## Generated documentation

If canonical documentation is generated, update the source and regenerate. Do not hand-edit output or
create a parallel manual copy.

## Cross-model portability

Do not encode vendor-specific internal tool names into canonical project governance unless the project
itself requires them. Express intent in model-neutral terms: inspect, search, validate, execute,
compare, update, and record evidence. Platform adapters may implement those operations differently.
