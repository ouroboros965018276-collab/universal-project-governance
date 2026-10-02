# Changelog

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
