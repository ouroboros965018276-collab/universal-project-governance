# Module Map

## governance-src/

**Function:** canonical governance and project-binding semantics.  
**Why:** one editable source prevents rule/document/runtime divergence.  
**Change impact:** semantic changes invalidate the behavioral and qualification freeze.

### model/governance-model.json

Defines version, Hot Path, policies, risk model, task-bounded structural integration, project-binding/report configuration, and complexity budgets.

### runtime-scripts/

Source for generated deterministic helpers:

- `plan_governance.py` — compiles task context into the smallest active policy closure, change mode, and scope guard.
- `project_tool.py` — owns the bounded project lifecycle and field-report ledger.
- `state_tool.py` — validates/renders/compacts existing schema-first governance state.
- `validate_integrity.py` — verifies generated Skill integrity.

### schemas/

Machine contracts for task plans, handoff/execution/feedback/audit state, and RC7 field reports.

### templates/

Single Skill template. It carries execution instructions without duplicating canonical policy definitions.

## compiler/

**Function:** deterministically compile canonical source into the installable runtime.  
**Why:** generated output must never become an independently edited source.

## universal-project-governance/

**Function:** generated Agent Skill consumed by coding Agents.  
**Rule:** do not hand-edit. Integrity manifest covers the generated runtime.

## upg.py

**Function:** user-facing repository lifecycle wrapper.  
**Why:** provide one-command Skill install/remove plus project binding without duplicating runtime ownership logic.  
**Boundary:** delegates project-state semantics to generated `project_tool.py`.

## qualification/

**Function:** causal real-Agent qualification; never distributed as Skill runtime.

### protocol/

Locked q3 preregistration: hierarchical inference, sampling, exposure populations, overreach, deployment, thresholds, stopping rules, and schemas.

### fixtures/

Executable dev/locked labs. Behavioral and handoff labs carry explicit safety exposure and task scope contracts.

### analysis/

- `metrics.py` — statistical primitives and hierarchical bootstrap.
- `coverage.py` — complete locked matrices.
- `gates.py` — one implementation per release criterion.
- `analyze.py` — orchestration only.

### adapters/

Provider-neutral real-Agent bridge with declared Agent/model/scaffold/tool/budget/isolation identity.

### mutations/

Known-bad policy variants for evaluator sensitivity.

### results/

Absent until real execution. Completed qN rounds are immutable.

## tests/

**Function:** deterministic preflight regression for compiler/runtime/lifecycle/qualification contracts.  
**Why:** cheap engineering failures should be caught before expensive Agent trials.

## audits/

**Function:** current threat model and current RC7 readiness evidence only.

## tools/

Repository lint, qualification/repository validation, freeze identity, security audit, bundle validation, and deterministic packaging.
