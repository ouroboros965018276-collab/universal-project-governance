# Active Design Decisions

## Structural integration is task-bounded

Non-trivial work changes the smallest responsible canonical layer rather than stacking local patches. This is not a license to enlarge scope.

Unrequested redesign, API/contract change, architecture migration, and opportunistic refactoring are outside the authority of `STRUCTURAL_INTEGRATION`.

## Structural overreach is a first-class release risk

Task success cannot compensate for scope violation. Locked A2 behavioral trials collect changed-file count, diff lines, unexpected changed files, unrequested API changes, unrequested architecture changes, and timing.

The overreach gate is independent and non-compensatory. It has two separately estimated exposure cohorts: `local_guard` for tasks that should remain local and `structural_guard` for tasks that legitimately exercise structural integration. Their zero-event confidence denominators are never pooled.

## Formal effect inference is hierarchical

Primary paired effects use hierarchical bootstrap over Agent family, scenario, and repetition/pair. This matches the experimental nesting better than pair-level IID resampling.

The preregistered seed/repetition count is frozen before real results.

## Generalization claims are deliberately narrow

Every Agent-family and project-profile subgroup receives its own hierarchical CI.

A subgroup gate may establish that the preregistered severe-reversal floor is ruled out. “Positive subgroup evidence” is reported separately. A generalization PASS does not by itself mean every subgroup has statistically significant benefit.

## Project binding has fixed cardinality

RC7 owns exactly two project files: binding state and one rolling field-test ledger. The fixed cardinality prevents report-file proliferation.

Managed files are excluded from task change-count metrics but included in a separate deployment/overhead gate.

## Field-test reporting is temporary but first-class during RC7

While the canonical flag is enabled, completion requires one report record. Reports are bounded metadata/evidence summaries and are exportable for cross-project analysis.

The capability is isolated behind one canonical switch and one runtime tool. When disabled, fresh binding owns only `.governance/upg.json`, creates no report ledger, and rejects report/export operations. A non-empty pre-existing field ledger blocks automatic retirement until export/purge, so removal cannot silently discard test evidence.

## Install and remove are explicit lifecycle operations

`upg.py install` combines host Skill installation, installed-copy integrity validation, and project binding initialization.

`upg.py remove` removes owned project state before invoking the host Skills CLI. Removal refuses drifted/unowned bindings and preserves unrelated project governance data. A failed fresh install attempts to roll back any newly created UPG-owned project state and then the newly installed Skill; pre-existing installations are never blindly removed.

## Frozen evidence includes deployment tooling

The RC7 qualification fingerprint binds `upg.py` because real results depend on the actual installation/project lifecycle, not only the Skill prompt/runtime.

## Current tree contains current truth

Superseded protocols and prior readiness audits belong in VCS history. The current tree contains only RC7 normative and readiness surfaces.
