---
name: universal-project-governance
description: Govern maintained-project changes by coupling implementation with proportional cleanup, current-state documentation, technical-debt control, chronology, validation, and handoff. Use when modifying code, configs, data, project docs, infrastructure, workflows, schemas, dependencies, migrations, or project structure. Do not use for read-only questions, analysis with no project change, or standalone one-off artifacts outside maintained project state.
license: Apache-2.0
compatibility: Core instructions require no runtime. Optional helpers use Python 3.8+ and git when available.
metadata:
  version: "2.0.0-rc.2"
  standard: "agentskills.io"
  maturity: "release-candidate"
  scope: "project-governance"
---

# Universal Project Governance

One Skill for implementation hygiene, maintenance, technical-debt control, documentation truth,
chronology, validation, and AI/engineer handoff. These are one lifecycle, not separate modes.

**Progressive disclosure changes what you load, not what you owe.** Apply every rule relevant to the
affected scope, while loading only the references needed for the task.

## Activation boundary

Use this Skill whenever you will change project state: source, configuration, infrastructure, data,
documentation, schemas, dependencies, workflows, generated-source inputs, prompts, models, or project
structure.

Do not activate it for purely read-only explanation, research, or Q&A that makes no project change.
For a tiny edit, use the smallest applicable path; do not map or reread the whole project by default.

If a specialized Skill is also active, let that Skill govern its domain workflow and use this Skill to
govern state integrity. Do not create competing sources of truth or invade another Skill's reserved
output namespace. See [interoperability](references/interoperability.md) when ownership overlaps.

## Non-negotiable invariants

1. **Change + cleanup** — every modification gets a proportional residue/duplication/staleness pass.
2. **Current truth** — normative docs describe what is true now; obsolete normative content is removed.
3. **Explainability** — significant units have discoverable function, purpose, boundaries, invariants,
   and change-safety information.
4. **No unmanaged debt** — safely fixable debt in the affected scope is fixed; blocked debt becomes a
   bounded, explicit exception. Never hide debt behind TODOs or comments.
5. **Evidence before claims** — do not call something unused, safe to delete, migrated, validated,
   compatible, debt-free, or current without evidence appropriate to that claim.
6. **Stable chronology** — preserve the latest and immediately previous meaningful change; use VCS for
   deep history when available.
7. **Handoff continuity** — durable project facts live in the project, not only in conversation memory.
8. **One source of truth** — reuse existing canonical structures; bootstrap templates only when no
   equivalent source exists.
9. **Proportional scope** — clean the affected neighborhood thoroughly without opportunistic rewrites of
   unrelated stable areas.
10. **No fabricated state** — unknown facts stay unknown; never invent timestamps, history, ownership,
    validation results, rationale, or deployment state.

## Core execution protocol

### 1. Orient only as far as the task requires

Identify the requested outcome, affected scope, nearest authoritative project instructions, canonical
sources of truth, relevant consumers/dependencies, and available validation. Prefer targeted reading
over a mandatory whole-repository tour.

For unfamiliar or cross-cutting projects, optionally run the scanner with the host's Python 3 executable (`python3` is shown below; use `python` where that is the platform convention):

```bash
python3 scripts/inspect_project.py /path/to/project --format markdown
```

The helper is evidence gathering, not a substitute for reasoning.

### 2. Define the end state

Before editing, make the target state clear enough to avoid parallel implementations:

- what becomes canonical;
- what is replaced or removed;
- what contract/invariant must remain true;
- what documentation/state record must change;
- what evidence will establish completion.

For migrations, compatibility layers, dependency changes, schema/API changes, or staged cutovers, load
[migrations and dependencies](references/migrations-and-dependencies.md).

### 3. Implement the requested outcome

Prefer established project abstractions when still appropriate. Do not add a new path when the correct
operation is to replace an old one. Preserve intentional compatibility only with a documented reason
and removal/permanence condition.

### 4. Close the cleanup loop

Inspect the affected neighborhood for duplicate implementation/config/docs, dead paths, obsolete
wrappers, stale flags, unused dependencies, orphaned tests/data/assets, generated drift, outdated
comments, renamed-path references, and temporary/debug residue.

Load [maintenance and cleanup](references/maintenance-and-cleanup.md) for non-trivial cleanup, deletion,
refactoring, or structural work. For Git working trees, `scripts/check_changed_refs.py` can surface
references to renamed/deleted paths for inspection.

### 5. Reconcile current truth

Update the project's existing canonical docs/state in the same task. Rewrite or remove contradictory
text instead of appending another version of the truth.

Load [documentation and truth](references/documentation-and-truth.md) when behavior, structure, naming,
interfaces, setup, operation, or architectural meaning changes.

If the project lacks equivalent governance state, bootstrap only the needed structures from `assets/`.
File names are defaults, not requirements; semantics are required.

### 6. Govern debt and uncertainty

Load [technical debt and exceptions](references/technical-debt-and-exceptions.md) whenever you encounter
legacy paths, temporary workarounds, unresolved defects, compatibility debt, unknown ownership, or a
constraint that prevents clean closure.

Use:
- `[TODO]` only for a factual gap that requires more evidence;
- `[ASK USER]` only when the correct choice depends on owner/team intent.

If either gap affects correctness, safety, data integrity, migration, or the requested acceptance
criteria, it blocks completion until resolved or explicitly accepted as a bounded exception.

### 7. Update chronology and continuity

For each meaningful change, roll `last change` into `previous change`, then write the new `last change`
with a timezone-aware time (or verified VCS anchor), what changed, why, before/after state, impact, and
validation. Do not scatter timestamps through source comments.

Load [chronology and handoff](references/chronology-and-handoff.md) for multi-module changes, releases,
handoffs, or projects without VCS.

### 8. Validate proportionally

Run the smallest set of checks that can establish the affected claims: static checks, focused tests,
contract/schema checks, build/render, data-quality checks, integration/runtime checks, documentation
checks, and diff review as applicable.

Load [validation and evidence](references/validation-and-evidence.md) when deleting, migrating,
asserting compatibility, handling generated/data artifacts, or making broad completion claims.

### 9. Pass the closure gate

A modifying task is complete only when all applicable closures pass:

- **Behavior closure** — requested outcome works.
- **Cleanup closure** — replaced, duplicate, obsolete, or temporary residue is removed or justified.
- **Truth closure** — canonical docs/state match the project now.
- **Evidence closure** — important claims are backed by actual checks/evidence.
- **Continuity closure** — chronology, invariants, and handoff context are sufficient for the next
  engineer or AI.

If a closure cannot pass, report the exact unresolved item and its boundary. Do not say "done" or
"debt-free" beyond the evidence you have.

## Reference router

Load only what the task needs:

| Need | Load |
|---|---|
| Cleanup, refactor, deletion, duplicate/obsolete content | [maintenance-and-cleanup.md](references/maintenance-and-cleanup.md) |
| Debt, temporary workaround, unknown, exception | [technical-debt-and-exceptions.md](references/technical-debt-and-exceptions.md) |
| Docs, module meaning, source-of-truth drift | [documentation-and-truth.md](references/documentation-and-truth.md) |
| Last/previous change, time, AI/engineer handoff | [chronology-and-handoff.md](references/chronology-and-handoff.md) |
| Tests, proof, deletion/migration evidence | [validation-and-evidence.md](references/validation-and-evidence.md) |
| Migration, schema/API/dependency/compatibility change | [migrations-and-dependencies.md](references/migrations-and-dependencies.md) |
| Data/ML/infra/docs/automation/monorepo or unusual project | [project-adaptation.md](references/project-adaptation.md) |
| Other Skills, generated docs, reserved namespaces | [interoperability.md](references/interoperability.md) |

## Project-state bootstrap

Only when no equivalent canonical structures already exist, use:

- `assets/PROJECT_STATE.md` — current state and rolling last/previous change;
- `assets/MODULE_MAP.md` — significant-unit function/purpose/contracts/invariants/change safety;
- `assets/DECISIONS.md` — only decisions still constraining the current design;
- `assets/EXCEPTIONS.md` — only active unresolved constraints;
- `assets/governance-state.schema.json` — optional machine-readable state instead of duplicate prose.

Do not create all of these automatically. Create the minimum truth surface the project actually needs.

## Default completion report

Keep the final report compact and factual:

- outcome and affected scope;
- cleanup/removals/consolidation performed;
- canonical docs/state synchronized;
- validation actually run and results;
- chronology updated;
- unresolved exception or verification gap, if any.

Phrase debt status precisely: **"No known unmanaged debt was introduced or left in the affected scope"**
only when supported. Never extrapolate a local review into a project-wide zero-debt claim.

## Final rule

Every change must leave the affected project state at least as coherent, current, explainable,
traceable, maintainable, and handoff-ready as it was before. Prefer removing obsolete complexity over
documenting around it, one current truth over parallel histories, and evidence over assumption.
