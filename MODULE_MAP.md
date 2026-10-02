# Module Map

> Significant repository units only. Generated caches/build outputs are not modules.

## Installable Skill
- **Location:** `universal-project-governance/`
- **Status:** release-candidate
- **Function:** Provides the model-agnostic governance contract, detailed references, bootstrap assets, and optional deterministic helpers.
- **Purpose:** Ensure maintained-project changes close implementation, cleanup, current truth, evidence, and continuity together.
- **Rationale:** One Skill prevents maintenance/documentation responsibilities from drifting into separately installed or inconsistently triggered policies; progressive disclosure controls context cost.
- **Scope:** Any maintained project state change; excludes read-only Q&A and unrelated one-off artifacts.
- **Inputs:** User task, project state, project instructions, observable evidence.
- **Outputs:** Governed project changes and durable project-state/handoff updates when applicable.
- **Dependencies / consumers:** Agent Skills-compatible hosts; optional Python 3.8+ and Git for helpers.
- **Invariants:** One Skill; model agnostic; evidence before destructive claims; no competing truth; current docs remain current.
- **Change safety:** Behavioral contract changes require eval updates and pre-release rerun; helper changes require multi-runtime tests.

### Last meaningful change
- **When:** 2026-10-02T20:28:00+08:00
- **Change ID:** rc2-clean-baseline
- **What / why:** Rebased the candidate into a clean repository layout and hardened helper safety without changing the core governance concept.
- **Before / after:** monolithic release bundle baseline → dedicated installable Skill inside a clean development repository.
- **Impact:** cleaner distribution and audit separation.
- **Validation:** local bundle/helper/security tests plus GitHub CI after upload.

### Previous meaningful change
- **When:** 2026-10-02T09:05:00+08:00
- **Change ID:** rc1-local-candidate
- **What / why:** Established the prior 2.0.0-rc.1 candidate and local release gates.
- **Before / after:** draft v2 → release candidate.
- **Impact:** supplied the audited baseline used for this clean rebuild.
- **Validation:** prior local audit; this repository does not inherit its Git history.

## Validation and Evaluation Harness
- **Location:** `tools/`, `tests/`, `evals/`
- **Status:** active-pre-release
- **Function:** Validates package structure, runtime helper behavior, security invariants, release reproducibility, triggers, and behavioral assertions.
- **Purpose:** Prevent format correctness from being mistaken for real quality and make release claims evidence-based.
- **Rationale:** Development/eval machinery is separated from the installed Skill to reduce user payload and avoid model-specific runtime coupling.
- **Scope:** Repository development and release pipeline only.
- **Inputs:** Skill source tree, fixtures, evaluation prompts.
- **Outputs:** pass/fail evidence, deterministic release package, audit findings.
- **Dependencies / consumers:** Python standard library locally; `skills-ref` and Skills CLI only in CI/release validation.
- **Invariants:** Tests must include negative cases; failed critical assertions block stable release; no hidden network requirement in runtime helpers.
- **Change safety:** Update corresponding tests/evals whenever observable governance behavior changes.

### Last meaningful change
- **When:** 2026-10-02T20:28:00+08:00
- **Change ID:** rc2-harness-hardening
- **What / why:** Moved evaluation/release tooling out of the installed Skill and added repository/security validation for cleaner distribution and stronger evidence.
- **Before / after:** self-contained RC1 bundle → separated runtime and development surfaces.
- **Impact:** smaller user-facing Skill and stronger release auditability.
- **Validation:** unit tests, security audit, deterministic package, CI.

### Previous meaningful change
- **When:** 2026-10-02T09:05:00+08:00
- **Change ID:** rc1-eval-suite
- **What / why:** Added 12 behavior eval cases and 20 trigger/near-miss cases.
- **Before / after:** structural checks only → prepared behavioral evaluation harness.
- **Impact:** stable promotion can be based on explicit assertions.
- **Validation:** JSON/schema/shape checks.

## CI and Release Pipeline
- **Location:** `.github/workflows/validate.yml`, `PUBLISHING.md`, `audits/`
- **Status:** active-pre-release
- **Function:** Runs authoritative upstream validation, runtime matrix, CLI installation tests, security checks, packaging checks, and records release evidence.
- **Purpose:** Make pre-release and stable claims reproducible and reviewable.
- **Rationale:** GitHub-hosted CI provides a fresh networked environment unavailable to local sandbox-only checks.
- **Scope:** Repository release engineering.
- **Inputs:** committed repository state.
- **Outputs:** GitHub Actions status/logs and audit record.
- **Dependencies / consumers:** GitHub Actions, `skills-ref==0.1.1`, `skills@1.7.0`.
- **Invariants:** least-privilege workflow permissions; no secret-dependent public test; stable remains blocked without behavioral evidence.
- **Change safety:** CI dependency or gate changes require a full rerun and audit update.

### Last meaningful change
- **When:** 2026-10-02T20:28:00+08:00
- **Change ID:** rc2-ci-clean-rebuild
- **What / why:** Rebuilt CI for the new repository and current action/CLI versions, including remote install smoke testing.
- **Before / after:** no CI in new repository → complete pre-release validation pipeline.
- **Impact:** enables fresh, repository-specific evidence.
- **Validation:** GitHub Actions run after initialization.

### Previous meaningful change
- **When:** N/A
- **Change ID:** N/A
- **What / why:** No previous CI exists in this new repository lineage.
- **Before / after:** N/A.
- **Impact:** None.
- **Validation:** New repository was empty before initialization.
