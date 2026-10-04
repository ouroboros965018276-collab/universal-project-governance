# Changelog

## 3.0.0-rc.12 — 2026-10-04

Qualification Evidence Refresh. Runtime governance semantics and qualification thresholds are unchanged from RC11.

- Refreshes five current micro-project functional checks and receipt verification under the installed RC12 Skill: 5/5 functional, 5/5 receipts, and 35/35 negative receipt cases rejected. Historical results remain one FAIL and four BLOCKED; no source, project report ledger, or historical record was backfilled.
- Executes the tenth registered formal RC12 development smoke on the final frozen fingerprint with Codex CLI 0.160.0. Registration, schema, artifact verification, and pre-inference release rejection pass; real-Agent execution still fails at host workspace-routing discovery before task changes. See [`qualification/dev-smoke/rc12.summary.json`](qualification/dev-smoke/rc12.summary.json).
- Produces two byte-identical RC12 runtime packages (SHA-256 `c65c0afa8cf16d73e349d8d2311b2c4dae614bb594c24205dcf3808029710125`); the local Codex Skill installation passes the same generated integrity manifest.
- Locked qualification remains NOT RUN; empirical qualification and Stable remain NOT ACHIEVED. This candidate does not promote development or functional evidence into release evidence.

## 3.0.0-rc.11 — 2026-10-04

- Makes field-test reporting explicitly opt-in for new project bindings, preserves existing enabled state and report history, and adds a top-level installer flag.
- Refuses to purge a ledger path when reporting is disabled and the binding does not own it, preventing accidental deletion of coincidentally named project data.
- Refuses to remove an opted-in project while its field-report ledger is non-empty; export and verified purge are required first.
- Makes planner output read the actual project binding; ordinary governance-note level no longer implies a field-report obligation.
- Adds a registered development-smoke path with real adapter identity, retained artifacts, A2 report integration, and a check that the release analyzer rejects development evidence before inference.
- Moves Skill installation and A2 report opt-in before the measured task baseline, fixing setup files being falsely counted as Agent overreach; applies explicit A2 opt-in to handoff trials too.
- Records the seventh registered RC11 dev-smoke as FAIL: the real Codex CLI turn failed at workspace routing before task changes; schema, artifact, and analyzer-boundary checks passed. See [`qualification/dev-smoke/rc11.summary.json`](qualification/dev-smoke/rc11.summary.json).
- Binds declared adapter helper-script bytes into runtime identity and adds a Codex CLI development adapter using the host project Skill discovery path.
- Adds a five-minute README quickstart, a concrete illustrative behavior comparison, and explicit limits on pilot, cost, domain, qualification, and Stable claims.
- Locked qualification gates remain unchanged; RC11 is not empirically qualified or Stable.

## 3.0.0-rc.10 — 2026-10-04

Pilot Evidence and Usability Hardening.

- Absorbs the owner-authorized top-down racing diagnostic pilot as a desensitized repository summary. Both A0 no-skill and A2 full-UPG arms passed the same 10/10 mechanical acceptance suite; this remains diagnostic field evidence only, not formal dev-smoke, locked qualification, empirical qualification, or Stable evidence.
- Closes the pilot feedback loop by making task-context risk dimensions schema-closed over the canonical risk model and by returning a clearer planner error for unknown keys such as legacy aliases.
- Separates ordinary plan report level from the field-test completion-report obligation in generated governance plans. `report: none` no longer looks like permission to skip the exactly-one field report while field-test reporting is enabled.
- Updates public evidence language to distinguish field-tested, formal dev-smoke validated, empirically qualified, and Stable states without weakening RC9/RC10 locked qualification gates.

## 3.0.0-rc.9 — 2026-10-03

Evidence and Continuity Hardening. RC8 baseline: `2127d022d3bb0db636324b0355ef307993486371`.

- Repairs fail-open evidence admission: frozen candidate/protocol, registered round/trial identity, schema constraints, fixture exposures/cohorts, model/adapter/host identities and retained artifact bytes are checked before inference.
- Integrates frozen identity, live verification and analysis settings into one qualification contract shared by registration planning, locked execution and evidence admission; removes duplicate checks and analyzer-only rejection. Empty evidence cannot bypass candidate drift rejection.
- Makes freeze and package ordering repository-relative and stable; compiler output uses LF on every platform. Adds Windows CI alongside Linux Python 3.8/3.11/3.13.
- Repairs wrongly escaped initial fixtures and requires their Python/JSON files to parse. Strengthens the chronology lab with trusted owner facts, explicit unknown history and actual task completion.
- Makes observed serious safety failures fatal even when an exposure tag is absent. A single invalid report cannot pass deployment.
- Adds stable workflow/event IDs, causal parents, sourced occurrence times, preserved active/latest/previous checkpoints, idempotent/conflict-safe retries and crash recovery. Explicit verified export precedes epoch rotation; sequence never resets. Old retries cannot rewind current truth.
- Preserves optional profile fallback and capability-based application with helpers unavailable. Rules remain 16, Hot Path 8, persistent managed files at most two; no new profiles or parallel history database.
- Adds 22 engineering regression cases (69 tests total). No real Agent or locked qualification results were produced in this phase.

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
