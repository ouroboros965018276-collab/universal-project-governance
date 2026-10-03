# Project State

Updated at: **2026-10-03T17:36:00+08:00**

## Purpose

Develop and empirically qualify one model-agnostic Agent Skill that improves maintained-project engineering behavior without turning governance itself into technical debt.

## Current candidate

**3.0.0-rc.7 — Real-Agent Test Freeze**

RC7 is engineering-valid on the private default branch, machine-frozen, and ready for real locked Agent qualification plus personal/friend gray testing.

## Current architecture

- `governance-src/` — one canonical definition of governance semantics and project-binding policy.
- `compiler/` — deterministic source-to-runtime compiler.
- `universal-project-governance/` — generated installable Skill; never hand-edit during normal work.
- `upg.py` — one-command project-scoped Skill install/remove wrapper with fresh-install rollback.
- `qualification/` — repository-only causal evidence system.
- `tests/` — deterministic runtime, lifecycle, scope, statistics, and qualification-contract regression tests.
- `audits/` — only the current threat model and current RC7 readiness audit.

## Current invariants

1. One semantic rule has one canonical definition.
2. Non-trivial work prefers structural integration, but structural mode is strictly task-bounded.
3. Structural mode never grants permission for unrelated redesign, API change, migration, or opportunistic refactor.
4. Structural overreach is evaluated in independent `local_guard` and `structural_guard` exposure cohorts; neither denominator may dilute the other.
5. UPG project state has fixed persistent cardinality: two managed files while RC7 field reporting is enabled.
6. Disabling field-test reporting produces a one-file binding for fresh projects and does not create a report ledger.
7. A non-empty existing RC7 report ledger cannot be silently retired; export/purge is required before reporting retirement.
8. RC7 completed modifying workflows create exactly one bounded field-test report record.
9. Reports contain metadata/evidence summaries, not source bodies, secrets, or private chain-of-thought.
10. Formal effect CIs use hierarchical Agent-family → scenario → repetition bootstrap.
11. Generalization reports subgroup CIs and does not conflate “no severe reversal” with “significant subgroup benefit.”
12. Stable gates use locked real-Agent evidence only; engineering tests cannot prove causal benefit.

## Latest meaningful change

- **Time:** 2026-10-03T17:36:00+08:00.
- **Change:** freeze-seal chronology correction after final audit.
- **Why:** the current-state documents still referenced main Run #109 even though the freeze-sealing commit `a471a358909c29a9f1ab28234f873f909d9f4ff0` was subsequently validated by Run #110.
- **What changed:** documentation/audit chronology only. No frozen runtime, protocol, fixture, analyzer, deployment, or qualification surface changed; all frozen fingerprints remain unchanged.
- **Validation state:** freeze-sealing Run #110 completed successfully with all 7 jobs passing; Python 3.8/3.11/3.13 each pass 43/43 tests; private default-branch clone/install and 16-file installed-copy integrity pass; deterministic Skill package SHA-256 is `794de7033d6ff4c556249499db1caff8033a7f1f746bd8d4f95c141109c54adf`.
- **Next safe action:** start real locked Agent and gray testing under qualification fingerprint `sha256:bc8727c209235d8a1a3b4bd2fe617753b82bdda7305ca8d6846f8081748757da` without changing frozen surfaces.

## Previous meaningful change

- **Time:** 2026-10-03T17:13:53+08:00.
- **Change:** final RC7 freeze hardening.
- **Why:** final audit found two residual lifecycle/statistical risks: scope-overreach confidence could combine qualitatively different local/structural exposures, and the field-report switch did not yet exercise a real no-ledger retirement path.
- **What changed:** split overreach into independent local/structural cohorts; made reporting-disabled binding actually omit the ledger and reject report operations; blocked silent retirement of non-empty evidence; added fresh-install project-state + Skill rollback; regenerated the deployment-bound freeze identity.
- **Carried forward:** hierarchical inference, subgroup CIs, task-bounded scope contracts, bounded field reports, automated lifecycle, and all RC6 qualification safeguards.
