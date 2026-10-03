# Active Design Decisions

Only current RC9 decisions are documented here.

## Continuity is reconstructable, not handoff-dependent

A deliberate unfinished transition should create one current factual handoff when possible. Abrupt interruption cannot be prevented reliably, so continuity may not depend on the previous actor successfully writing one.

A receiving actor reconstructs from canonical project truth, observable VCS/worktree or equivalent changes, validation evidence, UPG state, and unresolved artifacts. Unknown prior intent remains unknown. Private chat memory and chain-of-thought are not continuity dependencies.

## Legacy adoption is in place

UPG must become effective on a pre-existing maintained project without requiring a project-wide migration. Binding installation adds only UPG-owned state and preserves legacy project content.

Existing artifacts are evidence, not automatically authoritative architecture. Governance applies immediately to the current task while locating existing canonical truth and preserving observed contracts.

Owned RC7 binding state may upgrade to RC9 schema v2 without silently losing a report ledger.

## Agent interoperability is capability-negotiated

Vendor/model names do not determine behavior. An actor observes available host capabilities and uses only those it can actually exercise.

This permits conversational, coding, workspace/computer-use, IDE/CLI, browser/application, and future tool-using Agent classes to share one governance contract without a brittle vendor allowlist.

## Project-type profiles are hints, not forks

Named profiles activate relevant existing policies for common maintained-project forms. They do not create separate governance implementations.

Unknown or new project types remain governed by the universal Hot Path, default rules, task domains/signals, and risk model.

## Structural integration is task-bounded

Non-trivial work changes the smallest responsible canonical layer rather than stacking local patches. This never authorizes unrelated redesign, API/contract change, migration, or opportunistic refactoring.

## Structural overreach is independently gated

Task success cannot compensate for scope violation. `local_guard` and `structural_guard` have separate exposure/confidence denominators so one population cannot dilute the other.

## Formal effect inference remains hierarchical, with a stronger top-level claim guard

Primary paired effects bootstrap Agent family → scenario → repetition/pair. RC9 requires at least three locked Agent families.

Bootstrap repetition count does not manufacture independent top-level clusters. Cross-family generalization is therefore reported separately from within-family precision and subgroup claims remain deliberately narrow.

## Real-Agent execution identity is evidence

A trial condition is not identified by a human-written scaffold label alone. Locked evidence binds adapter configuration and implementation hashes plus host-tool name/version, alongside Agent/model/scaffold/tool/budget identity.

Cross-Agent handoff evidence records both source and receiving conditions.

## Completion reporting means exactly one

While field-test reporting is enabled, one completed modifying workflow must append exactly one report. The formal deployment gate checks `report_count == 1`; duplicate reports are a contract failure rather than acceptable evidence.

## Field-test reporting is bounded and privacy-conscious

RC9 still owns at most two project files during gray testing. Reports store bounded metadata/evidence summaries, not source contents or private reasoning.

Secret-pattern rejection is defense-in-depth for common private keys, tokens, Bearer/JWT-like values, assignment-style credentials, and credential-bearing database URLs. It is not represented as full DLP; export review remains required.

## Frozen evidence includes execution conditions

Qualification identity binds the runtime, protocol, fixtures, evaluators, adapters/runners, analyzer, and deployment wrapper. A semantic change to a frozen surface requires a new identity.

## Current tree contains current truth

Superseded protocols, readiness audits, and obsolete implementation notes belong in Git history rather than coexisting as parallel current documentation.

## RC9 chronology and reporting identity

Workflow IDs bind retries, active checkpoints, completion evidence, and latest/previous change references. Event IDs combine reporting epoch, workflow ID, and status; sequence is monotonic across purge. Explicit export must remain hash-verifiable before epoch rotation. The bounded ledger does not promise duplicate detection beyond an explicitly rotated retention epoch; archival evidence preserves that boundary. Runtime serializes mutations with a transient lock directory; abrupt-stop lock residue fails closed until an operator inspects and removes the stale lock. No persistent third state file is introduced.

Occurrence times require a source; unknown prior intent/time/commit remain unknown. Recorded timestamps do not establish causal order. Validate tested revision and reconcile current state before trusting an old handoff. When helpers are absent, the contract uses existing observable host state and reports its verification limits. Universal architecture is not a claim of empirically proven benefit across every domain.
