# Project State

> Canonical current-state overview for the Universal Project Governance repository. Deep history belongs in Git.

## Purpose

Develop, validate, audit, and publish one model-agnostic Agent Skill that keeps maintained-project
changes clean, current, evidenced, traceable, handoff-ready, and protected from accidental governance drift.

## Current state

The repository is a private pre-release workspace for **Universal Project Governance 2.0.0-rc.3**.
RC3 implements **Self-Protecting Governance + Feedback Driven Governance** while preserving the original
single-Skill concept. RC3 is now merged into `main`; structural, integrity, security, helper, package,
official-spec, local-install, and private-GitHub default-branch remote-install gates all pass. Stable/public
release remains intentionally blocked until real-agent trigger, behavior, cross-agent handoff, and
overhead qualification is completed.

## Architecture / structure

The repository has two deliberate layers:

- `universal-project-governance/`: the single installable Agent Skill, including integrity metadata,
  adaptive evidence/report policy, handoff/audit templates, and deterministic helpers;
- repository-level development surfaces (`tools/`, `tests/`, `evals/`, `.github/`, `audits/`,
  and governance docs): validation, behavioral evaluation, release engineering, and release evidence.

Repository-only tests/evals/audits are not installed into consumer projects.

## Canonical sources of truth

| Concern | Canonical source | Ownership / generation notes |
|---|---|---|
| Skill behavior contract | `universal-project-governance/SKILL.md` | Canonical normative Skill entry |
| Skill integrity policy | `universal-project-governance/INTEGRITY.md` + `integrity/` | Protect-all, tamper-evident |
| Detailed governance rules | `universal-project-governance/references/` | Progressive disclosure |
| Report/handoff templates | `universal-project-governance/assets/templates/` | Defaults; consumer equivalents may replace them |
| Repository current state | `PROJECT_STATE.md` | Current truth |
| Significant repository units | `MODULE_MAP.md` | Handoff map |
| Active design decisions | `DECISIONS.md` | Only decisions still constraining current design |
| Release gates | `PUBLISHING.md` | Stable/pre-release policy |
| Release evidence | `audits/` + GitHub Actions | Evidence, not normative behavior |
| Behavior evaluation | `evals/` | Fresh-context qualification assets |

## Major capabilities

| Capability | Current implementation | Status | Notes |
|---|---|---|---|
| Core governance lifecycle | `universal-project-governance/SKILL.md` | rc.3 | Original closure model retained + integrity closure |
| Tamper-evident Skill protection | `INTEGRITY.md`, `integrity/`, integrity scripts | rc.3 | Protect-all SHA-256 ledger |
| Adaptive reporting | report lifecycle reference + classifier | rc.3 | Minimal / standard / evaluation modes |
| Handoff continuity | handoff template + validator | rc.3 | Generated only at real continuation boundaries |
| Agent execution audit | execution audit template + policy | rc.3 | Evaluation/high-risk/explicit audit only |
| Governance feedback loop | feedback reference + template | rc.3 | Evidence-bearing signals only |
| Evidence export | `scripts/export_evidence_bundle.py` | rc.3 | Governance docs only; no source code by default |
| Structural/security validation | `tools/` + `tests/` | active | Repository-side quality tooling |
| Trigger/behavior evaluation | `evals/` | prepared | Real-agent runs still required before stable |
| CI validation | `.github/workflows/validate.yml` | active | Push/PR/manual dispatch |

## Constraints and invariants

- Exactly one installable Skill is maintained.
- The distributed Skill is model/vendor agnostic.
- All distributed Skill files except the generated checksum ledger are protected by the integrity model.
- Integrity is tamper-evident, not an authentication/security boundary against an actor with full write access.
- Ordinary project work must not regenerate Skill checksums.
- Reporting must be proportional; trivial changes must not create standalone report debt by default.
- Handoff state is current-state evidence and is overwritten, not accumulated indefinitely.
- Raw execution evidence is bounded; useful older evidence is summarized/archived before superseded raw records are removed.
- Official Agent Skills validation and supported helper runtimes must pass before release promotion.
- Static/install success is not proof of real-agent behavioral effectiveness.

## Validation / operation

| Purpose | Command or procedure | Expected evidence |
|---|---|---|
| Skill integrity | `python universal-project-governance/scripts/validate_integrity.py universal-project-governance` | PASS |
| Skill structure | `python tools/validate_skill_bundle.py universal-project-governance` | PASS |
| Repository integrity | `python tools/validate_repository.py .` | PASS |
| Security static audit | `python tools/security_audit.py .` | PASS |
| Helper/RC3 behavior | `python -m unittest discover -s tests -v` | All tests pass |
| Integrated governance | `python universal-project-governance/scripts/governance_check.py . --skill-root universal-project-governance` | PASS |
| Release package | `python tools/package_release.py universal-project-governance --output-dir dist` | Deterministic ZIP + SHA-256 |
| Upstream standard | GitHub CI `skills-ref==0.1.1` | PASS |
| Local installation | GitHub CI Skills CLI branch gate | Install + integrity PASS |
| Remote GitHub installation | GitHub CI on `main` | Install default branch + integrity PASS |

## Last meaningful change

- **When:** 2026-10-02T22:37:33+08:00
- **Change ID:** rc3-main-remote-install-verification
- **Scope:** default-branch release/install evidence
- **Before:** RC3 branch gates were green, but a true `owner/repo` install still resolved to RC2 because GitHub installs clone the repository default branch.
- **What changed:** merged tested RC3 through PR #1 into `main`, then ran the complete default-branch CI including private-GitHub remote clone/install and post-install integrity validation.
- **Why:** prove that users with repository access receive the actual RC3 bytes and that installation does not alter protected Skill content.
- **After:** RC3 engineering and installability gates are complete on `main`; only empirical real-agent behavior/handoff/overhead gates remain before stable/public promotion.
- **Impact:** closes the final deterministic pre-release installation gate without changing installed Skill bytes.
- **Validation:** GitHub Actions Run #26 completed successfully; remote repository clone, Skill discovery/install, and installed-copy integrity all passed; Python 3.8/3.11/3.13 each passed 19/19 tests; package SHA-256 remained `7cf5a301cb8cd4a9f576145418bd31ab6c65071a699ddc5d78081b7517df4580`.
- **Removed / superseded:** RC3 audit language that described remote GitHub installation as pending.

## Previous meaningful change

- **When:** 2026-10-02T22:28:00+08:00
- **Change ID:** rc3-self-protecting-feedback-governance
- **Scope:** installable Skill, integrity model, adaptive evidence/reporting, handoff, feedback, tests, release gates
- **Before:** RC2 governed project changes but did not protect itself from accidental agent edits and did not provide a bounded adaptive feedback/report lifecycle.
- **What changed:** added protect-all SHA-256 integrity, explicit Skill-upgrade authorization/version rules, minimal/standard/evaluation reporting, Handoff Snapshot, Agent Execution Audit, bounded retention, governance feedback, evidence export, validators, tests, and CI gates.
- **Why:** make cross-agent continuity auditable without forcing every small task to generate expensive persistent reports, while preventing ordinary agents from silently rewriting the governance contract.
- **After:** RC3 is self-protecting in the tamper-evident sense and can produce proportional review evidence without making the evidence system itself unbounded technical debt.
- **Impact:** governance behavior and release engineering; original maintenance/documentation/technical-debt concept remains intact.
- **Validation:** final RC3 branch CI passed all deterministic gates before merge; main Run #26 subsequently confirmed remote installability and integrity.

## Active exceptions

None in the RC3 implementation. Real-agent trigger/behavior qualification remains an intentional
stable-release gate, not an implementation debt exception.
