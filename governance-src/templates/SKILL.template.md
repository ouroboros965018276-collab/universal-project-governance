---
name: universal-project-governance
description: Govern maintained-project changes with a compiled, risk-adaptive plan that couples implementation, proportional cleanup, current truth, evidence, technical-debt control, and handoff continuity. Use for changes to code, config, data, docs, infrastructure, workflows, schemas, dependencies, migrations, generated sources, or project structure. Do not use for read-only Q&A or unrelated one-off artifacts.
license: Apache-2.0
compatibility: Core kernel needs no runtime. Optional deterministic planner/state/integrity helpers use Python 3.8+.
metadata:
  version: "{{VERSION}}"
  standard: "agentskills.io"
  maturity: "release-candidate"
  architecture: "compiled-governance"
---

# Universal Project Governance

A compiled governance runtime. The canonical governance model lives outside the installed Skill; this directory is generated and integrity-checked.

## Activation

Use for any maintained-project state change. Do not activate for read-only explanation/review/research that makes no project change.

## Hot path

{{HOT_PATH}}

## Execution

For a tiny, low-risk edit, apply the hot path directly and keep evidence proportional.

For non-trivial work, create a typed task context and compile the task-specific plan:

```bash
python3 scripts/plan_governance.py --context /path/to/task-context.json
```

The plan returns only the active rule closure, required evidence, report level, and whether handoff state is required. Execute that plan; do not load unrelated governance policy.

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
