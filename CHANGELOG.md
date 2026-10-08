# Changelog

## 3.0.0-rc.15 — 2026-10-08

Deterministic Skill Target Resolution. Qualification thresholds and the A0/A1/A2 protocol remain unchanged.

- Reproduces the top-level installer selecting a lexically earlier stale UPG copy when projects contain duplicates; regression tests cover the Codex canonical target, a unique non-Codex target, and ambiguous-copy refusal.
- Resolves Codex operations only through `.agents/skills/universal-project-governance`. An older/noncanonical copy counts as preexisting during install rollback so failed installation does not automatically remove preexisting project files.
- Regenerates the runtime and qualification freeze because `upg.py` is a frozen deployment surface. Windows Python 3.12 passed 105/105 tests; repository/freeze/bundle/integrity and security checks passed. Two independent packages match SHA-256 `6ac4d1a90ba640c1ec0ac974258cb0a678f0f8e105c348496fa3225e5a627128`. Hosted validation follows the branch head in draft [PR #14](https://github.com/ouroboros965018276-collab/universal-project-governance/pull/14); consult live checks for the current result.

## 3.0.0-rc.14 — 2026-10-08

Runtime Integrity and Diagnostic Hardening. Qualification thresholds and the A0/A1/A2 protocol remain unchanged.

- Consolidates public diagnostic redaction for both adapters, including URL userinfo, while preserving raw output only in local evidence storage; includes the helper in the Codex adapter runtime identity.
- Preserves Windows sandbox preflight timeout category, `timed_out` state, model-not-invoked boundary, and partial raw bytes. Reserves separate preflight, model-call, and outer-wrapper budget for the 900-second adapter.
- Makes reporting opt-in validation failure-neutral: invalid latest sequence/epoch leaves the reporting-off binding byte-identical and creates no ledger.
- Uses the canonical task-context schema for operation/domain/risk value validation while preserving the specific unknown-risk-dimension diagnostic and unknown-profile fallback.
- Adds URL-credential, preflight-timeout, timeout-budget, reporting-state, and default-mode partial-recovery regressions. The current full local run passed 101/101 tests on Blender-bundled CPython 3.13.13.
- Produces two byte-identical RC14 installable bundles, SHA-256 `60b2770e8c3cbc96c76081bf2504b3451349fc1141f4eb39f9e33c246145dd6b`. Compiler, lint, qualification, freeze (`sha256:e6e2bce7d6127655f49e88fd8d9e90e3ef2c0535c03fef1df5e2d6446d258b45`), repository, bundle, integrity, and security checks pass.
- Current RC14 development smoke passed registration/schema/artifact/analyzer-boundary checks but failed closed before model invocation because Windows sandbox provisioning is incomplete/outdated; see [`rc14-attempt-1.summary.json`](qualification/dev-smoke/rc14-attempt-1.summary.json). No model usage was incurred. The actual Codex Skill directory now matches the generated RC14 bundle and passed its temporary lifecycle task; the current session's Skills catalog still reports cached RC12. [Draft PR #13](https://github.com/ouroboros965018276-collab/universal-project-governance/pull/13) is open; verify CI against the live PR head before relying on it.

## 3.0.0-rc.13 — 2026-10-08

Runtime Completion and Diagnostics. Qualification thresholds and the frozen A0/A1/A2 protocol remain unchanged.

- Preserves Codex CLI inner stdout/stderr sidecars through the outer command adapter, records hashes and sanitized failure summaries, and distinguishes inner-task from wrapper timeouts. Windows sandbox preflight fails closed before inference and keeps raw diagnostics local.
- Adds a shared `finish` lifecycle command. Completed workflows update the existing latest/previous checkpoints when reporting is off and use the same exactly-once ledger reconciliation when reporting is on; no history database or extra managed project file is added.
- Validates all task-context fields against the canonical schema while retaining universal fallback for unknown optional profile hints.
- Regenerates the installable runtime and qualification freeze as RC13. Historical RC12 outcomes remain unchanged; this candidate does not claim locked qualification, empirical qualification, or Stable.
- Final local engineering verification passed 95/95 tests plus compiler, lint, qualification, repository, freeze (`sha256:31f754a18bd07cd07339eb148e726ac6df817032f71dc65506f63461e75234a7`), bundle, integrity, and security checks. Two independent Skill package builds matched SHA-256 `dcc8409381437051ffca0de5a143a5e63d066425b3f1d915ac8b982f72dbb2da`.
- The final registered A2 development smoke failed closed before model invocation because elevated Windows sandbox provisioning is incomplete; see [`rc13-attempt-3.summary.json`](qualification/dev-smoke/rc13-attempt-3.summary.json). An interrupted prior registration has no trial or usage result and remains explicitly unknown in [`rc13-attempt-2.summary.json`](qualification/dev-smoke/rc13-attempt-2.summary.json).

## RC12 prospective diagnostic record (2026-10-05, follow-up)

- Added path-free summaries for prospective Codex smoke attempts 13 and 14. Both exited 1 before usable task evidence; exact stderr and usage were not retained, so the cause remains unknown.
- Preserved the historical eleventh-smoke routing failure and the existing 1 FAIL + 4 BLOCKED governance result. Locked qualification remains NOT RUN; empirical qualification and Stable remain NOT ACHIEVED.

## RC12 prospective host diagnostic (2026-10-05)

- Docker Engine became reachable on the configured D: installation and successfully ran a container.
- Codex CLI Windows executable selection and process-environment routing now reach and complete the CLI turn; prospective attempt 12 still fails the task and A2 report checks with zero tool calls. Its adapter was uncommitted/unfrozen and host sandbox configuration was unrestricted, so it is diagnostic only; the prior attempt-11 history is unchanged.
- Historical acceptance remains 1 FAIL + 4 BLOCKED. Locked qualification remains NOT RUN; reviewed external isolation and three usable independent Agent families are still missing. Empirical qualification and Stable remain NOT ACHIEVED.
- Claude Code 2.1.289 and Gemini CLI 0.62.0 are installed on D: and report versions, but are unauthenticated and have not been run as Agents; family availability is not yet established.

## 3.0.0-rc.12 — 2026-10-04

Qualification Evidence Refresh. Runtime governance semantics and qualification thresholds are unchanged from RC11.

- Refreshes five current micro-project functional checks and receipt verification under the installed RC12 Skill: 5/5 functional, 5/5 receipts, and 35/35 negative receipt cases rejected. Historical results remain one FAIL and four BLOCKED; no source, project report ledger, or historical record was backfilled.
- Executes the eleventh registered formal RC12 development smoke on the final frozen fingerprint with Codex CLI 0.160.0. Registration, schema, artifact verification, and pre-inference release rejection pass; real-Agent execution still fails at host workspace-routing discovery before task changes. See [`qualification/dev-smoke/rc12.summary.json`](qualification/dev-smoke/rc12.summary.json).
- Produces two byte-identical RC12 runtime packages (SHA-256 `c65c0afa8cf16d73e349d8d2311b2c4dae614bb594c24205dcf3808029710125`); the local Codex Skill installation passes the same generated integrity manifest.
- Makes the hosted Skills CLI lifecycle job explicitly opt into field reporting before it exercises ledger export/removal, matching RC11's new-install default while retaining direct coverage of the opt-in path.
- Makes the top-level installer decode Skills CLI output as UTF-8 with replacement for malformed bytes, preventing Windows GBK locales from aborting on Unicode CLI output; adds a byte-level regression test.
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
\n
