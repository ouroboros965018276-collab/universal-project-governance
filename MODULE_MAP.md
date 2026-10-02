# Module Map

> Significant repository units only. Generated caches/build outputs are not modules.

## Installable Governance Skill
- **Location:** `universal-project-governance/`
- **Status:** 2.0.0-rc.3 release candidate
- **Function:** Governs maintained-project changes across implementation, cleanup, debt, current truth, chronology, validation, handoff, integrity, and proportional evidence.
- **Purpose:** Make each project change safe for the next AI/engineer without depending on hidden chat context.
- **Rationale:** One Skill keeps maintenance and documentation responsibilities inseparable; progressive disclosure controls context cost.
- **Scope:** Maintained project state changes; excludes read-only analysis and unrelated one-off artifacts.
- **Inputs:** User task, project state, authoritative instructions, observable evidence.
- **Outputs:** Governed project change, synchronized current truth, proportional evidence, and handoff state when required.
- **Dependencies / consumers:** Agent Skills-compatible hosts; Python 3.8+ and Git only for optional helpers.
- **Invariants:** One Skill; model agnostic; evidence before destructive claims; no competing truth; ordinary project work cannot modify the Skill.
- **Change safety:** Any Skill behavior change requires explicit governance-upgrade authorization, version/eval impact review, checksum refresh, and release-gate rerun.

### Last meaningful change
- **When:** 2026-10-02T22:28:00+08:00
- **Change ID:** rc3-self-protection-and-feedback
- **What / why:** Added integrity protection, adaptive reporting, handoff snapshot, execution audit, feedback loop, bounded retention, and evidence export so the Skill can protect and prove its own governance behavior.
- **Before / after:** project-governance protocol → tamper-evident, feedback-capable governance system.
- **Impact:** stronger cross-agent continuity with lower reporting overhead for small work.
- **Validation:** 19 tests × Python 3 runtimes, upstream spec, integrity, install, package reproducibility.

### Previous meaningful change
- **When:** 2026-10-02T20:28:00+08:00
- **Change ID:** rc2-clean-baseline
- **What / why:** Established clean repository/distribution separation and hardened helper safety.
- **Before / after:** local candidate → dedicated installable Skill + repository engineering layer.
- **Impact:** cleaner distribution and audit separation.
- **Validation:** RC2 CI and private remote installation.

## Skill Integrity and Evidence Layer
- **Location:** `universal-project-governance/INTEGRITY.md`, `integrity/`, report/feedback references, templates, RC3 helper scripts
- **Status:** active RC3
- **Function:** Detects distributed Skill drift, classifies report level, validates handoff/report retention, exports governance-only review evidence, and gates authorized Skill evolution.
- **Purpose:** Prevent accidental agent mutation and make governance observable without making every tiny edit expensive.
- **Rationale:** Read-only instructions alone cannot reveal whether the installed Skill drifted; unlimited execution reports would create governance debt.
- **Scope:** Distributed Skill integrity and optional consumer-project observability.
- **Inputs:** Installed Skill bytes; observable task scale/risk; optional `.governance/` state.
- **Outputs:** integrity PASS/FAIL, report classification, handoff/report validation, evidence bundle.
- **Dependencies / consumers:** Python standard library; VCS is optional except frozen-audit diff checking.
- **Invariants:** checksum refresh requires explicit upgrade confirmation; checksums never auto-refresh during validation; evidence export excludes project source by default; raw execution retention is bounded.
- **Change safety:** Treat all files under the Skill root as protected except the generated checksum ledger itself.

### Last meaningful change
- **When:** 2026-10-02T22:28:00+08:00
- **Change ID:** rc3-integrity-ledger
- **What / why:** Introduced protect-all SHA-256 ledger generated on a clean runner and enforced it in CI and installed copies.
- **Before / after:** policy-only self-protection → executable tamper-evident validation.
- **Impact:** accidental or partial Skill edits become detectable before use/release.
- **Validation:** tamper test fails as expected; authorized refresh test; installed Skill integrity PASS.

### Previous meaningful change
- **When:** 2026-10-02T21:38:00+08:00
- **Change ID:** rc2-evidence-anchor
- **What / why:** Anchored release identity to package digest and CI provenance.
- **Before / after:** prose-oriented evidence → content-identity evidence.
- **Impact:** supports RC3 external trust anchor.
- **Validation:** RC2 deterministic package/CI provenance was independently verified before RC3 development.

## Validation and Evaluation Harness
- **Location:** `tools/`, `tests/`, `evals/`
- **Status:** active pre-release
- **Function:** Validates structure, integrity prerequisites, runtime helper behavior, security invariants, reproducible packaging, trigger cases, and behavior assertions.
- **Purpose:** Prevent static validity from being mistaken for real quality.
- **Rationale:** Development/eval machinery stays outside the installed Skill.
- **Scope:** Repository development and release only.
- **Inputs:** Skill tree, fixtures, eval prompts.
- **Outputs:** pass/fail evidence and deterministic package.
- **Dependencies / consumers:** Python standard library; upstream `skills-ref` and Skills CLI in CI.
- **Invariants:** negative tests included; critical behavior failure blocks stable; package validation includes integrity validation.
- **Change safety:** Behavior changes require matching tests/evals.

### Last meaningful change
- **When:** 2026-10-02T22:28:00+08:00
- **Change ID:** rc3-test-expansion
- **What / why:** Expanded suite from 11 to 19 tests with integrity tamper, refresh authorization, report policy, handoff, retention, and evidence-export cases.
- **Before / after:** RC2 helper tests → RC3 governance-system tests.
- **Impact:** new RC3 mechanisms are executable and regression-tested.
- **Validation:** 19/19 on Python 3.8, 3.11, 3.13.

### Previous meaningful change
- **When:** 2026-10-02T20:28:00+08:00
- **Change ID:** rc2-harness-hardening
- **What / why:** Separated runtime and repository test surfaces.
- **Before / after:** self-contained release bundle → lean installed Skill + external dev harness.
- **Impact:** lower installation noise.
- **Validation:** RC2 helper, package, security, and installation gates passed on the clean repository baseline.

## CI and Release Pipeline
- **Location:** `.github/workflows/validate.yml`, `PUBLISHING.md`, `audits/`
- **Status:** active pre-release
- **Function:** Runs official spec, three Python runtimes, security/integrity checks, local install, deterministic package, and main-branch remote installation.
- **Purpose:** Make release claims reproducible and attributable.
- **Rationale:** Branch CI must validate the candidate bytes; default-branch remote installation can only truthfully be tested after merge.
- **Scope:** Repository release engineering.
- **Inputs:** committed repository state.
- **Outputs:** GitHub Actions evidence and frozen release audits.
- **Dependencies / consumers:** GitHub Actions, `skills-ref==0.1.1`, `skills@1.7.0`.
- **Invariants:** least privilege; no automatic checksum refresh; remote GitHub install runs only on `main`; stable remains behavior-gated.
- **Change safety:** gate changes require full rerun.

### Last meaningful change
- **When:** 2026-10-02T22:28:00+08:00
- **Change ID:** rc3-ci-integrity
- **What / why:** Added installed-Skill integrity validation and corrected branch remote-install semantics.
- **Before / after:** branch CI could accidentally test RC2 default branch as RC3 → branch validates local candidate, main validates real remote install.
- **Impact:** CI evidence now corresponds to the bytes actually under test.
- **Validation:** RC3 branch CI passes after correction.

### Previous meaningful change
- **When:** 2026-10-02T21:38:00+08:00
- **Change ID:** rc2-audit-anchor-hardening
- **What / why:** Removed self-referential audit run/commit requirement.
- **Before / after:** recursive audit churn → stable content-identity evidence.
- **Impact:** cleaner release pipeline.
- **Validation:** RC2 pre-release workflow completed successfully with package and installation evidence.
