---
name: universal-project-governance
description: Govern maintained-project changes with a compiled, risk-adaptive plan that couples structural integration, proportional cleanup, current truth, evidence, technical-debt control, and handoff continuity. Use for changes to code, config, data, docs, infrastructure, workflows, schemas, dependencies, migrations, generated sources, or project structure. Do not use for read-only Q&A or unrelated one-off artifacts.
license: Apache-2.0
compatibility: Core kernel needs no runtime. Optional deterministic planner/state/integrity helpers use Python 3.8+.
metadata:
  version: "3.0.0-rc.6"
  standard: "agentskills.io"
  maturity: "release-candidate"
  architecture: "compiled-governance"
---

# Universal Project Governance

A compiled governance runtime. The canonical governance model lives outside the installed Skill; this directory is generated and integrity-checked.

## Activation

Use for any maintained-project state change. Do not activate for read-only explanation/review/research that makes no project change.

## Hot path

1. **ONE_CURRENT_TRUTH** — Reuse one canonical source of truth; update or remove obsolete normative state instead of creating parallel truth.
2. **PROPORTIONAL_CLEANUP** — Every project change gets cleanup proportional to its affected neighborhood; remove replaced, duplicate, temporary, or stale residue when safe.
3. **EVIDENCE_BEFORE_CLAIM** — Deletion, migration, compatibility, validation, and debt/completion claims require evidence appropriate to the claim.
4. **NO_FABRICATION** — Unknown facts stay unknown; never invent history, timestamps, ownership, rationale, validation, deployment state, or consumer intent.
5. **NO_UNMANAGED_DEBT** — Safely fixable in-scope debt is fixed; externally blocked debt becomes a bounded exception with risk and removal/review condition.
6. **VALIDATE_AFFECTED** — Run the smallest sufficient checks that establish the affected behavior, cleanup, truth, and contract claims.
7. **HANDOFF_IF_UNFINISHED** — If work crosses an agent/session boundary or remains unfinished, persist current handoff state in the project rather than chat memory.
8. **STRUCTURAL_INTEGRATION** — Except for truly local low-risk edits, change the responsible canonical structure and remove superseded patch paths instead of stacking shims, duplicate branches, one-off flags, or detached fixes.

## Execution

For a truly local low-risk edit, apply the hot path directly and keep evidence proportional. Do not manufacture architecture work for a typo or equivalent isolated correction.

For non-trivial work, prefer structural integration at the responsible canonical layer over patch stacking. Remove superseded shims, duplicate branches, temporary compatibility paths, and detached fixes when safe.

Create a typed task context and compile the task-specific plan:

```bash
python3 scripts/plan_governance.py --context /path/to/task-context.json
```

The plan returns the change mode (`local` or `structural`), active rule closure, required evidence, report level, and whether handoff state is required. Execute that plan; do not load unrelated governance policy.

If helpers are unavailable, read `policy-index.json` and apply only rules matching the task operation/domains/signals plus their `requires` closure.

## Risk context

Use observable facts, not model confidence. Risk dimensions are scope, reversibility, security, data impact, external consumers, migration, contract change, unknowns, and handoff need. File/line counts are secondary signals only.

## Evidence and reports

Do not create a permanent report for every task.

- `none`: concise final response/VCS evidence is enough.
- `change-note`: compact persistent note only if the project needs it.
- `engineering`: maintain `.governance/execution/latest.json`.
- `audit`: use a frozen release/audit record.

Schema-first governance state is canonical. Markdown is a rendered view, not a second editable truth. Use `scripts/state_tool.py` to validate/render/compact/export governance state.

A current handoff is required only when work is unfinished or actually crosses an agent/session boundary. Keep at most one current handoff.

## Integrity

This installed runtime is generated. During ordinary project work do not edit it.

```bash
python3 scripts/validate_integrity.py .
```

If integrity fails, stop treating the modified runtime as authoritative. Authorized Skill evolution happens in canonical governance source, followed by compilation, complexity/static checks, tests, install validation, and a new audit candidate.

## Completion

A modifying task is complete only when applicable behavior, cleanup, truth, evidence, continuity, and integrity obligations in the compiled plan are satisfied. State unresolved blockers precisely; never expand a local review into a project-wide debt-free claim.

## Interoperability

Respect existing project sources of truth and specialized Skills. Governance semantics may live in existing canonical project structures; do not create parallel documentation merely to match a filename.

## Final rule

Governance capability may grow, but runtime cognitive load must remain bounded. One semantic rule has one canonical definition; complexity belongs in the compiler, not in agent context.
