# Project State

Updated at: **2026-10-03T14:17:00+08:00**

## Purpose

Develop and empirically qualify one model-agnostic Agent Skill that improves maintained-project engineering behavior while preventing governance itself from becoming technical debt.

## Current candidate

**3.0.0-rc.6 — Structural Integration & Qualification Hardening**

The project is in engineering validation before real locked Agent qualification.

## Current architecture

- `governance-src/` — one canonical definition of governance semantics.
- `compiler/` — deterministic source-to-runtime compiler.
- `universal-project-governance/` — generated installable Skill; never hand-edit during normal work.
- `qualification/` — repository-only causal evidence system.
- `tests/` — deterministic runtime and qualification-contract regression tests.
- `audits/` — only the current threat model and current RC6 readiness audit.

## Current invariants

1. One semantic rule has one canonical definition.
2. Tiny local low-risk edits may remain local.
3. Non-trivial work defaults to structural integration at the responsible canonical layer.
4. Replaced patches, shims, duplicate paths, stale truth, temporary work, and obsolete artifacts are removed when safe.
5. Claims require evidence appropriate to the claim.
6. Qualification Stable gates use locked evidence only.
7. Critical-safety denominators are exposure-specific; trigger/mutation trials cannot inflate them.
8. A1 attention control must be measured and valid before A2>A1 governance-uplift claims.
9. Stable requires 8+ complete locked repetitions per scenario × Agent-family cell.
10. Real result rounds are immutable and cannot be replaced by edited templates.

## Latest meaningful change

- **Change:** RC6 structural upgrade.
- **Why:** pre-qualification review found safety-denominator contamination, incomplete matrix enforcement, weak subgroup generalization, unenforced handoff/artifact/control thresholds, and an overly permissive 5-repetition Stable path.
- **What changed:** governance runtime gained one structural-integration semantic; qualification was decomposed into explicit independent gates and evidence contracts; obsolete RC-specific layers were removed.
- **Validation state:** deterministic CI pending final regenerated runtime/freeze and full matrix tests.
- **Handoff rule:** do not start real locked qualification until RC6 final CI is green and `qualification/FREEZE.json` is regenerated.

## Previous meaningful change

- **Time:** 2026-10-03T04:20:14+08:00 (VCS commit time).
- **Change:** RC5 qualification framework freeze.
- **Why:** separate internal compiler correctness from causal real-Agent effectiveness.
- **Outcome carried forward:** paired A0/A1/A2 design, executable holdouts, trigger/handoff/mutation qualification, evidence-first grading, and machine fingerprints remain foundational.
