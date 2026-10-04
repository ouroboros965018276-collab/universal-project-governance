# Module Map

Current candidate: **3.0.0-rc.12**.

This map describes the current tree only. Historical implementations belong in Git history.

## governance-src/

**Function:** canonical governance, interoperability, project-binding, and field-report semantics.  
**Why it exists:** one editable source prevents policy/runtime/document drift.  
**Change rule:** semantic changes require regeneration, full validation, and a new qualification identity.

### model/governance-model.json

**Function:** canonical version, Hot Path, policy graph, risk model, task-bounded structural integration, binding v2, and complexity budgets.  
**Why:** runtime behavior must have one authoritative machine-readable definition.

### profiles/

**Function:** optional project-type activation hints.  
**Why:** different maintained-project forms benefit from different policy emphasis without forking governance semantics.  
**Current coverage:** software, data, infrastructure, ML/AI, automation, docs/knowledge, design systems, research/evidence, content/editorial, product/specification, operations/runbooks, and mixed projects.  
**Boundary:** an unknown type still works through universal defaults and task/risk triggers; profiles are not an allowlist.

### runtime-scripts/

Source for generated deterministic helpers:

- `plan_governance.py` — compiles typed task context into the smallest active rule closure, risk, change mode, scope guard, evidence, report level, field-report obligation, and handoff obligations.
- `project_tool.py` — owns bounded binding v2 lifecycle, non-destructive legacy adoption, opt-in reporting, status/report/export/purge/remove, and field-report secret hygiene.
- `state_tool.py` — validates/renders/compacts/exports schema-first governance state.
- `validate_integrity.py` — checks generated Skill integrity.

### schemas/

Machine contracts for task context/plans, handoff, execution, feedback, audit, and field reports.

### templates/

Single installable-Skill instruction template. It defines the Agent operating contract without duplicating canonical policy bodies.

## compiler/

**Function:** deterministic canonical-source → installable-runtime compilation.  
**Why:** `universal-project-governance/` must never become an independently edited truth.

## universal-project-governance/

**Function:** compiler-generated Agent Skill consumed by host systems.  
**Rule:** never hand-edit. Integrity manifest covers the generated runtime.

The runtime uses capability negotiation rather than vendor-specific behavior and supports in-place adoption plus handoff-or-reconstruct continuity.

## upg.py

**Function:** one-command project-scoped install/status/export/purge/remove wrapper.  
**Why:** expose a simple lifecycle without duplicating ownership semantics.  
**Boundary:** project state remains delegated to generated `project_tool.py`; failed fresh installs attempt owned-state and Skill rollback.

## qualification/

**Function:** repository-only causal real-Agent qualification. Never shipped as runtime.

### protocol/

The q3 protocol: minimum three Agent families, hierarchical inference, safety exposures, structural-overreach cohorts, deployment/report rules, reproducibility identity, thresholds, and stopping rules. Formal dev smoke is registered separately and never release-admitted.

### fixtures/

Development and locked labs, including cross-domain trigger cases and handoff tasks. Fixtures carry explicit scope and safety contracts. `qualification/lib/contracts.py` supplies the canonical frozen candidate and settings contract to round planning, locked execution and evidence admission; the analyzer dispatches that admission gate.

### analysis/

- `metrics.py` — pairing/statistical primitives and hierarchical bootstrap.
- `coverage.py` — locked matrix completeness plus adapter/host identity requirements.
- `gates.py` — one non-compensatory implementation per release criterion, including exactly-one completion reporting.
- `analyze.py` — orchestration only.

### adapters/

**Function:** provider/host-neutral bridge to real Agents.  
**Identity:** Agent/model/scaffold, adapter config SHA-256, adapter runtime SHA-256, host-tool name/version, capabilities, tool profile, budget profile, and isolation.  
**Cross-Agent handoff:** source and receiving execution identities are both preserved.

### mutations/

Known-bad policy variants used to prove evaluator sensitivity.

### results/

Absent until real execution. Completed locked rounds are immutable.

### pilots/

Desensitized diagnostic field-pilot summaries. These records may explain what was learned and what was absorbed, but they are not locked qualification results and do not contain source bodies or raw traces.

## tests/

**Function:** deterministic preflight regression for compiler/runtime, binding/adoption, privacy hygiene, qualification contracts, statistics, and lifecycle.  
**Why:** cheap engineering defects must be found before expensive or user-facing trials.

## audits/

**Function:** current threat model and current RC9 readiness evidence only. Superseded readiness audits do not stay in the current tree.

## tools/

Repository/governance/qualification validation, freeze identity, security audit, bundle validation, and deterministic packaging.
