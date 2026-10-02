---
name: universal-project-governance
description: Govern maintained-project changes by coupling implementation with proportional cleanup, current-state documentation, technical-debt control, chronology, validation, handoff, integrity protection, and adaptive audit feedback. Use when modifying code, configs, data, project docs, infrastructure, workflows, schemas, dependencies, migrations, or project structure. Do not use for read-only questions, analysis with no project change, or standalone one-off artifacts outside maintained project state.
license: Apache-2.0
compatibility: Core instructions require no runtime. Optional deterministic helpers use Python 3.8+ and git when available.
metadata:
  version: "2.0.0-rc.3"
  standard: "agentskills.io"
  maturity: "release-candidate"
  scope: "project-governance"
---

# Universal Project Governance

One model-agnostic Skill for implementation hygiene, cleanup, technical-debt control, documentation
truth, chronology, validation, handoff continuity, governance integrity, and evidence feedback.

**Progressive disclosure changes what you load, not what you owe.** Load only the references needed
for the task, but do not weaken applicable invariants.

## Activation boundary

Use this Skill whenever you will change maintained project state: source, configuration,
infrastructure, data, documentation, schemas, dependencies, workflows, generated-source inputs,
prompts, models, or project structure.

Do not activate it for purely read-only explanation, research, review, or Q&A that makes no project
change. For a tiny edit, use the smallest applicable path; do not map or reread the whole repository
by default.

If a specialized Skill is active, let it own its domain workflow while this Skill governs resulting
project-state integrity. Do not create competing sources of truth or invade another Skill's reserved
namespace. See [interoperability](references/interoperability.md).

## Non-negotiable invariants

1. **Change + cleanup** — every modification gets a proportional residue, duplication, and staleness pass.
2. **Current truth** — normative docs describe what is true now; obsolete normative content is removed.
3. **Explainability** — significant units have discoverable function, purpose, boundaries, invariants,
   dependencies, and change-safety information.
4. **No unmanaged debt** — safely fixable debt in scope is fixed; externally blocked debt becomes a
   bounded exception with evidence and a removal/review condition.
5. **Evidence before claims** — do not call something unused, safe to delete, migrated, validated,
   compatible, debt-free, or current without evidence appropriate to that claim.
6. **Stable chronology** — preserve the latest and immediately previous meaningful change; use VCS for
   deeper history when available.
7. **Handoff continuity** — durable facts live in the project, not only in conversation memory.
8. **One source of truth** — reuse existing canonical structures; bootstrap templates only when no
   equivalent source exists.
9. **Proportional scope** — clean the affected neighborhood thoroughly without unrelated rewrites.
10. **No fabricated state** — never invent timestamps, history, ownership, validation, rationale, or deployment state.
11. **Protected governance** — the installed Skill is read-only during normal project work. Do not
    modify its files unless the user explicitly asks to upgrade or repair the Skill itself. See
    [INTEGRITY.md](INTEGRITY.md).

## Session integrity check

When deterministic helpers are available, check Skill integrity once at the start of a project-changing
session, after installation/update, or whenever protected Skill files appear modified:

```bash
python3 scripts/validate_integrity.py .
```

Do not rerun this before every tiny edit. Integrity is **tamper-evident**, not a substitute for host
permissions, VCS review, signed releases, or an external package digest.

If integrity fails during an ordinary project task, stop treating the modified Skill as authoritative
and report the mismatch. Do not silently regenerate checksums.

## Core execution protocol

### 1. Orient only as far as the task requires

Identify the requested outcome, affected scope, nearest authoritative instructions, canonical sources
of truth, relevant consumers/dependencies, and available validation. Prefer targeted reading over a
mandatory whole-repository tour.

For unfamiliar or cross-cutting work, optionally run:

```bash
python3 scripts/inspect_project.py /path/to/project --format markdown
```

The scanner provides signals, not conclusions.

### 2. Define the end state

Before editing, establish:

- what becomes canonical;
- what is replaced or removed;
- what contracts/invariants must remain true;
- what documentation/state record must change;
- what evidence will establish completion.

For migrations, compatibility layers, dependency, schema, or API changes, load
[migrations and dependencies](references/migrations-and-dependencies.md).

### 3. Implement the requested outcome

Prefer established abstractions when still appropriate. Do not add a parallel path when replacement
is the correct operation. Retain compatibility only with an explicit reason and removal/permanence
condition.

### 4. Close the cleanup loop

Inspect the affected neighborhood for duplicate implementation/config/docs, dead paths, obsolete
wrappers, stale flags, unused dependencies, orphaned tests/data/assets, generated drift, outdated
comments, renamed-path references, and temporary/debug residue.

Load [maintenance and cleanup](references/maintenance-and-cleanup.md) for non-trivial cleanup,
deletion, refactoring, or structural work.

### 5. Reconcile current truth

Update existing canonical docs/state in the same task. Rewrite or remove contradictions instead of
appending another version of the truth.

Load [documentation and truth](references/documentation-and-truth.md) when behavior, structure,
naming, interfaces, setup, operation, or architectural meaning changes.

### 6. Govern debt and uncertainty

Load [technical debt and exceptions](references/technical-debt-and-exceptions.md) for legacy paths,
temporary workarounds, unresolved defects, compatibility debt, unknown ownership, or blocked cleanup.

Use:
- `[TODO]` only for a factual gap requiring more evidence;
- `[ASK USER]` only when the correct choice depends on owner/team intent.

If either gap affects correctness, safety, data integrity, migration, or acceptance criteria, it
blocks completion until resolved or explicitly accepted as a bounded exception.

### 7. Maintain continuity and handoff

For every meaningful change, roll `last change` to `previous change`, then record the new meaningful
change with a verified time or VCS anchor, what changed, why, before/after state, impact, and validation.

Create or refresh a **Handoff Snapshot** when there is an actual handoff boundary: another agent or
engineer will continue, the task remains partially complete, important constraints changed, or the
user explicitly wants handoff state. Do not generate a new handoff file for every typo.

Load [chronology and handoff](references/chronology-and-handoff.md) and use
[the handoff template](assets/templates/HANDOFF.md) when needed.

### 8. Validate proportionally

Run the smallest set of checks that can establish affected claims: static checks, focused tests,
contract/schema checks, build/render, data-quality checks, integration/runtime checks,
documentation checks, and diff review as applicable.

Load [validation and evidence](references/validation-and-evidence.md) for destructive, migration,
compatibility, generated/data, or broad completion claims.

### 9. Select the evidence/report level

Reporting is adaptive, not mandatory bureaucracy. Load
[report lifecycle policy](references/report-lifecycle-policy.md) for non-trivial work, explicit audit
requests, handoffs, or evaluation/testing.

Default modes:

- **minimal** — no standalone report for trivial low-risk work; VCS + concise completion note is enough.
- **standard** — current-state docs stay synchronized; standalone Engineering Reports appear only when
  risk/scale warrants them.
- **evaluation** — used while testing the Skill or when the user wants richer evidence; qualifying work
  also produces an Agent Execution Audit and governance feedback signals.

If helper scripts are available, `scripts/classify_report.py` can classify the appropriate level from
observable task facts. The classification is guidance; domain risk can override numeric thresholds.

### 10. Capture feedback only when it teaches something

Do not log generic praise or routine success. Create governance feedback only for useful signals such as:

- user correction of the agent;
- validation/rollback failure caused by governance behavior;
- repeated ambiguity or missing rule;
- over-triggering or excessive ceremony;
- handoff failure;
- a rule that causes duplicate truth or blocks safe work.

Load [feedback loop](references/feedback-loop.md). Feedback may propose a Skill change, but it may not
modify protected Skill files during an ordinary project task.

### 11. Pass the closure gate

A modifying task is complete only when all applicable closures pass:

- **Behavior** — requested outcome works.
- **Cleanup** — replaced/duplicate/obsolete/temporary residue is removed or justified.
- **Truth** — canonical docs/state match reality now.
- **Evidence** — important claims are backed by actual checks.
- **Continuity** — chronology, invariants, and handoff context are sufficient for the next agent/human.
- **Governance integrity** — the Skill itself was not silently changed.

If a closure cannot pass, report the exact unresolved item and boundary. Do not say "done" or
"debt-free" beyond the evidence available.

## Reference router

| Need | Load |
|---|---|
| Cleanup, refactor, deletion, duplicate/obsolete content | [maintenance-and-cleanup.md](references/maintenance-and-cleanup.md) |
| Debt, workaround, unknown, exception | [technical-debt-and-exceptions.md](references/technical-debt-and-exceptions.md) |
| Docs, module meaning, source-of-truth drift | [documentation-and-truth.md](references/documentation-and-truth.md) |
| Last/previous change, time, handoff | [chronology-and-handoff.md](references/chronology-and-handoff.md) |
| Tests, proof, deletion/migration evidence | [validation-and-evidence.md](references/validation-and-evidence.md) |
| Migration, schema/API/dependency/compatibility | [migrations-and-dependencies.md](references/migrations-and-dependencies.md) |
| Data/ML/infra/docs/automation/monorepo | [project-adaptation.md](references/project-adaptation.md) |
| Other Skills or reserved namespaces | [interoperability.md](references/interoperability.md) |
| Report level, retention, audit lifecycle | [report-lifecycle-policy.md](references/report-lifecycle-policy.md) |
| Feedback capture and Skill improvement evidence | [feedback-loop.md](references/feedback-loop.md) |
| Versioning and authorized Skill evolution | [version-policy.md](references/version-policy.md) |

## Project-state bootstrap

Only when no equivalent canonical structures already exist, use:

- `assets/PROJECT_STATE.md` — current state and rolling last/previous change;
- `assets/MODULE_MAP.md` — significant-unit function/purpose/contracts/invariants/change safety;
- `assets/DECISIONS.md` — only decisions still constraining current design;
- `assets/EXCEPTIONS.md` — only active unresolved constraints;
- `assets/templates/HANDOFF.md` — current handoff snapshot, overwritten when refreshed;
- `assets/templates/AGENT_EXECUTION_AUDIT.md` — evidence-oriented execution audit for qualifying tasks;
- `assets/governance-state.schema.json` — optional machine-readable state instead of duplicate prose.

Do not create all files automatically. Reuse existing project structures first.

## Evidence export for review

When the user wants an external audit (for example, to send evidence to another reviewer), use
`scripts/export_evidence_bundle.py` if available. It exports governance documents and recent
governance reports only; it does not export source code or secret-like files by default.

## Default completion report

Keep the normal final response compact:

- outcome and affected scope;
- cleanup/removals/consolidation performed;
- canonical docs/state synchronized;
- validation actually run and results;
- chronology/handoff updated when applicable;
- unresolved exception or verification gap, if any.

Use the precise debt statement **"No known unmanaged debt was introduced or knowingly left in the
affected scope"** only when supported. Never extrapolate a local review into a project-wide zero-debt
claim.

## Final rule

Every change must leave the affected project at least as coherent, current, explainable, traceable,
maintainable, and handoff-ready as before. The governance system must reduce project debt without
becoming governance debt itself.
