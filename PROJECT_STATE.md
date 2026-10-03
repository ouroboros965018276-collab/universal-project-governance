# Project State

Updated at: **2026-10-03T15:43:54+08:00**

## Purpose

Develop and empirically qualify one model-agnostic Agent Skill that improves maintained-project engineering behavior without turning governance itself into technical debt.

## Current candidate

**3.0.0-rc.7 — Real-Agent Test Freeze**

RC7 engineering validation is complete and the candidate is machine-frozen for real locked Agent qualification.

## Current architecture

- `governance-src/` — one canonical definition of governance semantics and project-binding policy.
- `compiler/` — deterministic source-to-runtime compiler.
- `universal-project-governance/` — generated installable Skill; never hand-edit during normal work.
- `upg.py` — repository convenience entry point for one-command Skill + project lifecycle.
- `qualification/` — repository-only causal evidence system.
- `tests/` — deterministic runtime, lifecycle, scope, and qualification-contract regression tests.
- `audits/` — only the current threat model and current RC7 readiness audit.

## Current invariants

1. One semantic rule has one canonical definition.
2. Non-trivial work prefers structural integration, but structural mode is strictly task-bounded.
3. Structural mode never grants permission for unrelated redesign, API change, migration, or opportunistic refactor.
4. UPG project state has fixed persistent cardinality: at most two managed files in RC7.
5. Managed UPG files are preserved during ordinary cleanup and removed only through explicit uninstall.
6. RC7 completed modifying workflows create exactly one bounded field-test report record.
7. Reports contain metadata/evidence summaries, not source bodies, secrets, or private chain-of-thought.
8. Formal effect CIs use hierarchical Agent-family → scenario → repetition bootstrap.
9. Generalization reports subgroup CIs and does not conflate “no severe reversal” with “significant subgroup benefit.”
10. Stable gates use locked real-Agent evidence only; engineering tests cannot prove causal benefit.

## Latest meaningful change

- **Time:** 2026-10-03T15:38:07+08:00.
- **Change:** RC7 real-Agent test freeze architecture.
- **Why:** final engineering review identified IID bootstrap optimism, weak subgroup claim semantics, structural-overreach risk, and the need for foolproof field deployment/report collection.
- **What changed:** hierarchical inference, subgroup CIs, task-bounded structural scope contracts, an independent overreach gate, two-file project binding, bounded field reports, automated lifecycle, and deployment-bound qualification identity.
- **Validation state:** Run #93 is green; Python 3.8/3.11/3.13 each pass 41/41 tests; lifecycle/install/integrity/security/package gates pass; RC7 freeze identity is current.
- **Next safe action:** start real locked Agent and gray testing under the current fingerprint without changing frozen surfaces.

## Previous meaningful change

- **Time:** 2026-10-03T14:46:17+08:00.
- **Change:** RC6 engineering validation completed.
- **Why:** close qualification correctness gaps before empirical testing.
- **Carried forward:** class-specific critical-safety exposure, complete locked matrix requirements, attention-control validity, handoff degradation measurement, artifact overhead, and bounded compiled runtime.
