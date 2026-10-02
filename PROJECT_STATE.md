# Project State

> Canonical current-state overview for the Universal Project Governance repository. Deep history belongs in Git.

## Purpose

Develop, validate, audit, and publish one model-agnostic Agent Skill that keeps maintained-project changes clean, current, evidenced, traceable, and handoff-ready.

## Current state

The repository is a private pre-release workspace for **Universal Project Governance 2.0.0-rc.2**. The installable Skill is present under `universal-project-governance/`. Engineering/installability gates are implemented and passing on the current candidate; stable/public release remains intentionally blocked until real-agent trigger and behavior gates are completed.

## Architecture / structure

The repository has two deliberate layers:

- `universal-project-governance/`: the single installable Agent Skill and its runtime/reference assets;
- repository-level development surfaces (`tools/`, `tests/`, `evals/`, `.github/`, `audits/`, and governance docs): validation, behavioral evaluation, release engineering, and evidence.

This separation keeps user installations small and avoids shipping repository-only CI/audit machinery as part of the Skill.

## Canonical sources of truth

| Concern | Canonical source | Ownership / generation notes |
|---|---|---|
| Skill behavior contract | `universal-project-governance/SKILL.md` | Canonical normative Skill entry |
| Detailed governance rules | `universal-project-governance/references/` | Loaded progressively from SKILL.md |
| Project current state | `PROJECT_STATE.md` | Repository-level current truth |
| Significant repository units | `MODULE_MAP.md` | Repository-level handoff map |
| Active architectural decisions | `DECISIONS.md` | Only decisions still constraining current design |
| Release gates | `PUBLISHING.md` | Stable/pre-release policy |
| Observable release evidence | `audits/` + GitHub Actions | Audit evidence, not normative behavior |
| Behavioral evaluation cases | `evals/` | Development/evaluation assets, not runtime Skill content |

## Major capabilities

| Capability | Current implementation | Status | Notes |
|---|---|---|---|
| Core governance lifecycle | `universal-project-governance/SKILL.md` | release candidate | Five closure gates + non-negotiable invariants |
| Detailed domain rules | `universal-project-governance/references/` | release candidate | Progressive disclosure |
| Deterministic evidence helpers | `universal-project-governance/scripts/` | release candidate | Read-only by default; Python 3.8+ target |
| Structural/security validation | `tools/` + `tests/` | release candidate | Repository-side quality tooling |
| Trigger/behavior evaluation | `evals/` | prepared | Requires real-agent execution before stable |
| CI validation | `.github/workflows/validate.yml` | active | Runs on push/PR/manual dispatch |

## Constraints and invariants

- Exactly one installable Skill is maintained.
- The Skill remains model/vendor agnostic; host-specific validation stays outside the installable Skill.
- Current-state docs describe the present repository, not historical snapshots.
- Official Agent Skills validation and supported helper runtimes must pass before any release promotion.
- Static/installation success is not treated as proof of behavioral effectiveness.
- Public/stable release is blocked while critical behavioral or safety evidence remains unverified.
- Candidate audit identity must not require self-referential commit/run metadata that causes documentation-only churn.

## Validation / operation

| Purpose | Command or procedure | Expected evidence |
|---|---|---|
| Skill structure | `python tools/validate_skill_bundle.py universal-project-governance` | PASS, no errors |
| Repository integrity | `python tools/validate_repository.py .` | PASS, no errors |
| Security static audit | `python tools/security_audit.py .` | PASS, no critical findings |
| Helper behavior | `python -m unittest discover -s tests -v` | All tests pass |
| Self-governance | `python universal-project-governance/scripts/validate_project_governance.py .` | Governance docs pass |
| Release package | `python tools/package_release.py universal-project-governance --output-dir dist` | Deterministic ZIP + SHA-256 |
| Upstream standard | GitHub CI `skills-ref==0.1.1` job | PASS |
| Installation | GitHub CI Skills CLI smoke job | Local + repository install PASS |

## Last meaningful change

- **When:** 2026-10-02T21:38:00+08:00
- **Change ID:** rc2-audit-anchor-hardening
- **Scope:** release governance and audit evidence
- **Before:** release policy required an audit document to embed the exact commit and CI run, causing self-referential documentation churn.
- **What changed:** candidate identity is now anchored to version + deterministic installable-package SHA-256 + successful CI for the current release-relevant HEAD; audit prose no longer needs to contain its own future commit/run identifiers.
- **Why:** preserve strict evidence while eliminating an impossible/infinite audit-update loop.
- **After:** release evidence is immutable enough for verification without creating technical debt through repeated audit-only commits.
- **Impact:** release-policy/audit surfaces only; installable Skill semantics and candidate bytes remain unchanged.
- **Validation:** full repository CI is required after this release-policy change.
- **Removed / superseded:** self-referential exact-commit/run audit requirement.

## Previous meaningful change

- **When:** 2026-10-02T20:28:00+08:00
- **Change ID:** initial-pre-release-baseline
- **Scope:** repository-wide
- **Before:** new empty repository
- **What changed:** established the clean Universal Project Governance 2.0.0-rc.2 pre-release repository, separated installable Skill from repository-only validation assets, and hardened the candidate for fresh CI/audit.
- **Why:** create a clean publication lineage with no unrelated legacy-repository history.
- **After:** one private pre-release repository dedicated only to Universal Project Governance.
- **Impact:** established the canonical project lineage and release pipeline.
- **Validation:** GitHub Actions and private remote installation passed.
- **Removed / superseded:** unrelated legacy repository lineage is not inherited.

## Active exceptions

None in the repository implementation. Stable-release behavioral evidence gates remain intentionally open; they are release criteria, not technical-debt exceptions.
