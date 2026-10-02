# Changelog

## 2.0.0-rc.3 — 2026-10-02

Self-Protecting Governance + Feedback Driven Governance release candidate.

- Adds protect-all tamper-evident integrity checks for the distributed Skill.
- Adds explicit authorization/version/checksum gates for Skill evolution.
- Adds adaptive report selection so trivial edits do not create report debt.
- Adds Handoff Snapshot, Agent Execution Audit, and governance feedback semantics.
- Adds bounded retention and evidence export for external audit.
- Adds executable integrity, report, handoff, evidence-export, and orchestration helpers.
- Keeps the original single-Skill, model-agnostic project-governance concept intact.
- Stable promotion remains blocked pending real-agent trigger and behavior qualification.

## 2.0.0-rc.2 — 2026-10-02

Clean-repository pre-release candidate. Core governance semantics remain unchanged from rc.1; this candidate hardens distribution, validation, and helper safety.

- Starts from a new repository lineage dedicated only to Universal Project Governance.
- Separates installable Skill content from repository-only CI, eval, test, audit, and release tooling.
- Preserves the single-Skill model and progressive-disclosure references.
- Hardens changed-path reference scanning to skip symlinked files/directories.
- Broadens conservative secret-like filename exclusion in project inspection.
- Adds repository self-governance (`PROJECT_STATE.md`, `MODULE_MAP.md`, `DECISIONS.md`, `AGENTS.md`).
- Adds repository-level structure, version, eval, license, and security validation.
- Uses current tested GitHub Actions major versions and `skills@1.7.0` install smoke tests.
- Keeps stable release blocked pending real-agent trigger and behavioral baseline evaluation.

## 2.0.0-rc.1 — 2026-10-02

Prior local candidate used as the content baseline for this clean rebuild. Its Git history is intentionally not inherited by this repository.
