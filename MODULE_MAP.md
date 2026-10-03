# Module Map

## governance-src/

**Function:** canonical governance semantics.  
**Why it exists:** one editable source of truth for Policy IR, risk semantics, structural-integration activation, schemas, templates, and runtime helper sources.  
**Do not:** hand-edit generated runtime to bypass this layer.

### governance-src/model/governance-model.json

Defines the 3.0.0-rc.6 governance model, 8 Hot Path invariants, 16 policies, risk model, structural-integration activation, and complexity budgets.

### governance-src/runtime-scripts/

Source for deterministic runtime helpers. Changes here are behavior changes and invalidate the behavioral fingerprint.

### governance-src/schemas/

Contracts for task context, governance plans, handoff, execution, feedback, and audit state.

### governance-src/templates/

The single Skill template. It explains activation/execution without duplicating Policy definitions.

## compiler/

**Function:** deterministically compile canonical governance source into the installable runtime.  
**Why it exists:** generated output must be reproducible and drift-detectable.

## universal-project-governance/

**Function:** installable Agent Skill.  
**Why it exists:** this is the bounded runtime consumed by coding Agents.  
**Rule:** generated only; ordinary project work must not modify it.

## qualification/

**Function:** causal real-Agent qualification.  
**Why it exists:** prove or falsify benefit without increasing runtime load.

### qualification/protocol/

Locked v2 preregistration: arms, sampling, safety exposure semantics, gate order, thresholds, schemas, and stopping rules.

### qualification/fixtures/

Executable development and locked holdout repositories plus multilingual trigger families. Labs declare `safety_exposures`; handoff labs also declare checkpoint preservation contracts.

### qualification/analysis/

- `metrics.py` — statistical primitives only.
- `coverage.py` — locked matrix and handoff matrix completeness.
- `gates.py` — release criteria; each criterion has one implementation.
- `analyze.py` — thin orchestrator and CLI.

This split exists so statistical meaning is not hidden inside one monolithic analyzer.

### qualification/adapters/

Provider-neutral bridge to real coding Agents. Formal adapters declare isolation, model/scaffold, tool/budget profiles, and measured usage.

### qualification/mutations/

Known-bad policy variants used to validate evaluator sensitivity before trusting release conclusions.

### qualification/graders/

Blind outcome packaging for semantic judgments that cannot be established deterministically.

### qualification/results/

Not populated by templates. Real qN evidence rounds appear here only after execution and are immutable.

## tests/

**Function:** deterministic engineering regression.  
**Why it exists:** catch runtime/compiler/qualification-contract defects before expensive Agent trials.

`tests/fixtures/governance_plan_cases.json` is the canonical deterministic planner case set.

## audits/

**Function:** current release-readiness evidence and current threat model only.  
**Why it exists:** keep release blockers explicit without turning the tree into a historical report archive.

## tools/

Repository-level deterministic validation, packaging, security audit, governance lint, freeze generation/checking, and current-tree validation.
