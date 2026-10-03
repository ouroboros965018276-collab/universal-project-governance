# Project State

Current candidate: **3.0.0-rc.9 — Evidence and Continuity Hardening**.

## Current purpose and architecture

One bounded, project/model/host-agnostic governance Skill. Canonical semantics live in `governance-src/`; the compiler generates `universal-project-governance/`. Qualification remains repository-only. Managed state remains the binding and bounded report ledger; Git/current project sources supply durable history.

## Latest observed change

- Event: RC9 evidence-and-continuity remediation; base revision `2127d022d3bb0db636324b0355ef307993486371`.
- Observation time: 2026-10-03T13:20:33.332472Z, local UTC acceptance checkpoint. This is neither the original start time nor the Git commit time. Original work-start time is unknown; the active runtime checkpoint was observed at `2026-10-03T12:51:59.340996Z`.
- Why: owner requested repair of reproduced RC8 audit gaps, a broadly reusable Skill, local Codex installation and engineering acceptance; real Agent tests are excluded this phase.
- Before/after: RC8 accepted mismatched evidence identities and weak chronology/report conditions; RC9 rejects invalid admission, fixes portable freeze/fixtures/safety, and preserves task identity, causal parents and observable handoff continuity.
- How: repair responsible source/compiler/qualification layers, regenerate runtime, add negative engineering regressions, freeze the new identity and validate installation. No new domain policies or project-wide redesign.
- Validation: local Windows Python 3.12 runs 69 engineering tests. Audit's machine record and CI links are the authoritative checkpoint evidence; local success is not claimed as remote success.
- Candidate commit: the Git commit containing this checkpoint; no self-referential guessed SHA is embedded. Match its frozen fingerprint with `qualification/FREEZE.json` before using evidence.

## Previous observed state

- Previous Git change: `2127d022d3bb0db636324b0355ef307993486371`, committed `2026-10-03T11:07:15Z` (GitHub metadata), documentation alignment after RC8 freeze. RC8 implementation was squash commit `8f963843`; detailed intent/time inside the squash is not reconstructed without source evidence.
- Prior document stated meaningful checkpoint times `2026-10-03T19:06:41+08:00` and `2026-10-03T18:54:06+08:00`. Retained as stated times, not silently promoted to observed code/commit times.
- Prior audit: local Windows 44/47 original tests, three cross-platform failures, evidence-chain reproductions. This remediation is causally based on that audit and the owner's RC9 instruction.

## Completion and next boundary

No real Agent, dev-smoke or locked result round is executed in this phase. Stable is blocked. The next phase must verify actual adapters/isolation/model identity, externally seal its round plan, review budgets and retained private evidence, and only then execute the frozen protocol. Runtime breadth is an architectural contract; the current locked software/data matrix does not prove every domain's efficacy.

Unknown facts remain unknown. Inspect active checkpoints and observed changes after interruption; do not fabricate intent, timestamps or validation. Preserve causal parent/sequence across export and explicitly bounded epoch rotation. Stale lock/temp residue requires factual reconciliation before recovery.

## Follow-up to observed Windows CI

Checkpoint observed 2026-10-03T13:20:36.274819Z (local UTC; original edit-start time unknown). Previous candidate `31896578b73ae0207d2a1bf8d35ad8ff5608b4a7` was committed `2026-10-03T13:11:15Z` according to GitHub metadata. Run #189 passed seven jobs but its two Windows jobs failed because Chinese trigger JSON could not be written through cp1252 stdout. This follow-up preserves Unicode data through ASCII JSON transport, adds the matching negative-environment regression, and verifies live frozen surfaces before locked execution/inference. Function/reason/source are documented in the readiness record; the runtime remains bounded. Local suite is now 69 tests; a new remote CI is required before promotion.
