# Module Map

## Canonical Governance Source
- **Location:** `governance-src/`
- **Status:** active / canonical
- **Function:** Defines all governance semantics, profiles, schemas, runtime helper source, and presentation template.
- **Purpose:** Provide one independently editable source of governance truth.
- **Rationale:** Prevent natural-language rule drift and duplicate semantic definitions.
- **Scope:** Maintainer engineering; not installed as runtime source material.
- **Inputs:** Explicit governance changes.
- **Outputs:** Inputs consumed by the compiler.
- **Dependencies / consumers:** compiler, linter, tests.
- **Invariants:** one rule ID → one definition; profiles activate only; IR has no executable DSL semantics.
- **Change safety:** semantic changes require version/eval/audit review and full compile/CI.

### Last meaningful change
- **When:** 2026-10-03
- **Change ID:** rc4-source-model
- **What / why:** replaced RC3 cross-linked reference prose with typed canonical Policy IR.
- **Before / after:** Markdown-centric rule maintenance → one typed machine-readable model.
- **Impact:** removes manual semantic synchronization.
- **Validation:** schema/graph/static analysis and compiler drift tests.

### Previous meaningful change
- **When:** 2026-10-02
- **Change ID:** rc3-reference-model
- **What / why:** progressive-disclosure references organized RC3 governance details.
- **Before / after:** monolithic prompt → routed reference documents.
- **Impact:** reduced context cost but retained cognitive/maintenance complexity.
- **Validation:** RC3 audit.

## Governance Compiler and Static Analysis
- **Location:** `compiler/`, `tools/governance_lint.py`
- **Status:** active
- **Function:** Compiles canonical source into runtime and rejects deterministic governance defects.
- **Purpose:** Move complexity out of agent context and make governance structure mechanically testable.
- **Rationale:** Compilers can absorb source complexity while preserving a small runtime contract.
- **Scope:** build/release pipeline.
- **Inputs:** canonical source.
- **Outputs:** generated runtime, lint findings.
- **Dependencies / consumers:** Python standard library, CI.
- **Invariants:** deterministic output; no hidden network; cycles/orphans/conflicts/budget violations fail.
- **Change safety:** compiler behavior changes require generated-runtime drift review and multi-runtime tests.

### Last meaningful change
- **When:** 2026-10-03
- **Change ID:** rc4-compiler
- **What / why:** introduced source→runtime compilation and Governance Complexity Gate.
- **Before / after:** agent assembled reference rules → deterministic active-rule closure.
- **Impact:** bounded runtime cognitive load and stronger self-governance.
- **Validation:** compiler --check, linter, tests, CI.

### Previous meaningful change
- **When:** 2026-10-02
- **Change ID:** rc3-deterministic-validation
- **What / why:** RC3 added integrity/report/handoff validators.
- **Before / after:** prose-only rules → executable checks.
- **Impact:** enabled RC4 compiler evolution.
- **Validation:** RC3 CI.

## Generated Runtime Skill
- **Location:** `universal-project-governance/`
- **Status:** generated release candidate
- **Function:** Supplies the compact hot-path kernel, compiled policy index, typed schemas, plan compiler, state tooling, and runtime integrity check to agent clients.
- **Purpose:** Keep installed context small while preserving full governance capability.
- **Rationale:** runtime complexity must remain approximately bounded even as source capabilities grow.
- **Scope:** distributed/installable Skill only.
- **Inputs:** compiler output.
- **Outputs:** task-specific Governance Plans and structured governance state.
- **Dependencies / consumers:** Agent Skills-compatible clients; optional Python 3.8+ helpers.
- **Invariants:** never hand-edit; compiler output must match tracked runtime exactly; `SKILL.md` ≤120 lines.
- **Change safety:** modify canonical source, regenerate, then validate.

### Last meaningful change
- **When:** 2026-10-03
- **Change ID:** rc4-runtime-contraction
- **What / why:** removed runtime references/assets and reduced `SKILL.md` to a compact compiled kernel.
- **Before / after:** 256-line SKILL + reference/template trees → generated 82-line kernel + typed policy index/schemas.
- **Impact:** materially lower agent cognitive/context load.
- **Validation:** compiler drift, complexity budget, upstream Agent Skills validation, Skills CLI install.

### Previous meaningful change
- **When:** 2026-10-02
- **Change ID:** rc3-runtime
- **What / why:** RC3 added integrity/report/handoff capabilities to the installed Skill.
- **Before / after:** RC2 governance protocol → self-protecting/feedback-driven runtime.
- **Impact:** functionality preserved and compiled into RC4.
- **Validation:** RC3 audit.

## Evaluation and Release Pipeline
- **Location:** `tests/`, `evals/`, `.github/workflows/validate.yml`, `PUBLISHING.md`, `audits/`
- **Status:** active pre-release
- **Function:** Validates compiler, risk plans, schemas, compaction, integrity, complexity, installation, packaging, and behavioral release gates.
- **Purpose:** Separate engineering correctness from empirical agent effectiveness.
- **Rationale:** valid format/installability does not prove real-agent behavior.
- **Scope:** repository development/release.
- **Inputs:** source/runtime changes and eval cases.
- **Outputs:** CI evidence and candidate audit.
- **Dependencies / consumers:** GitHub Actions, Python, skills-ref, Skills CLI.
- **Invariants:** static gates cannot substitute for real-agent behavioral qualification.
- **Change safety:** release-gate changes require full CI and audit synchronization.

### Last meaningful change
- **When:** 2026-10-03
- **Change ID:** rc4-release-gates
- **What / why:** added plan cases, graph/complexity gates, schema-state tests, generated-runtime checks.
- **Before / after:** RC3 document/runtime checks → compiled-source/runtime qualification.
- **Impact:** release process now detects governance meta-complexity.
- **Validation:** GitHub Actions.

### Previous meaningful change
- **When:** 2026-10-02
- **Change ID:** rc3-pre-release-gates
- **What / why:** multi-runtime, upstream validation, CLI install, integrity/evidence gates.
- **Validation:** RC3 main CI.
