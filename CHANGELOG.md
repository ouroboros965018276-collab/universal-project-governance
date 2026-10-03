# Changelog

## 3.0.0-rc.9 — 2026-10-03

Evidence and Continuity Hardening. RC8 baseline: `2127d022d3bb0db636324b0355ef307993486371`.

- Repairs fail-open evidence admission: frozen candidate/protocol, registered round/trial identity, schema constraints, fixture exposures/cohorts, model/adapter/host identities and retained artifact bytes are checked before inference.
- Makes freeze and package ordering repository-relative and stable; compiler output uses LF on every platform. Adds Windows CI alongside Linux Python 3.8/3.11/3.13.
- Repairs wrongly escaped initial fixtures and requires their Python/JSON files to parse. Strengthens the chronology lab with trusted owner facts, explicit unknown history and actual task completion.
- Makes observed serious safety failures fatal even when an exposure tag is absent. A single invalid report cannot pass deployment.
- Adds stable workflow/event IDs, causal parents, sourced occurrence times, preserved active/latest/previous checkpoints, idempotent/conflict-safe retries and crash recovery. Explicit verified export precedes epoch rotation; sequence never resets. Old retries cannot rewind current truth.
- Preserves optional profile fallback and capability-based application with helpers unavailable. Rules remain 16, Hot Path 8, persistent managed files at most two; no new profiles or parallel history database.
- Adds 21 engineering regression cases (68 tests total). No real Agent or locked qualification results were produced in this phase.

## 3.0.0-rc.8 — 2026-10-03

Universal Continuity Real-Agent Test Freeze.

- Makes continuity reconstructable after abrupt interruption: a receiving actor can recover from project truth, observable work state, validation evidence, UPG state, and explicit unknowns even when no formal handoff was written.
- Adds non-destructive in-place adoption for projects that predate UPG. Binding v2 records adoption/continuity/capability semantics while preserving legacy project content and existing RC7 field-test evidence.
- Replaces vendor/class assumptions with observable capability negotiation so conversational, coding, workspace/computer-use, CLI/IDE, browser/application, and future tool-using Agents share one contract.
- Broadens maintained-project coverage with research/evidence, content/editorial, product/specification, and operations/runbook domains/profiles while keeping unknown project types on the universal fallback path.
- Raises locked qualification from two to at least three Agent families and explicitly narrows cross-family claims because bootstrap repetitions cannot create independent top-level clusters.
- Binds locked trial evidence to adapter configuration SHA-256, adapter runtime SHA-256, host-tool name/version, and both source/receiving identities for cross-Agent handoff trials.
- Enforces the declared completion invariant formally: exactly one field report per completed modifying workflow.
- Extends field-report secret hygiene to common Bearer/JWT-like tokens, assignment-style credentials, and credential-bearing database URLs while retaining bounded metadata-only reporting.
- Preserves RC7 task-bounded structural integration, independent overreach cohorts, subgroup CIs, automated lifecycle, deterministic compilation, and fixed managed-state cardinality.

## Previous meaningful state — 3.0.0-rc.7

RC7 established hierarchical Agent-family → scenario → repetition inference, subgroup confidence intervals, task-bounded structural integration, independent overreach cohorts, automated two-file project binding/report lifecycle, and the first machine-frozen real-Agent qualification identity. RC8 preserves those foundations and closes interruption, legacy-adoption, cross-Agent reproducibility, and exact-reporting gaps before real testing.
