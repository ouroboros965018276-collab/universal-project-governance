# Project State

Current candidate: **3.0.0-rc.9 — Evidence and Continuity Hardening**.

RC9 repairs the audited evidence and continuity gaps. The latest task-bounded integration makes `qualification/lib/contracts.py` the canonical authority for frozen identity, live surface verification and finite JSON analysis settings. Registration planning, locked execution and evidence admission consume that authority; analysis dispatches the admission gate rather than maintaining a separate configuration rejection path. No real Agent/dev-smoke/locked qualification round has run. Stable remains blocked pending the separate real-agent phase.

## Current change and why

Observation: 2026-10-03T14:03:08.697711Z, local UTC checkpoint; original edit-start unknown. Parent revision: `683b1ff0f85b36e9db38557d893051dcbc29ba50`, Git time `2026-10-03T13:46:36Z`. Before: equivalent freeze checks were repeated across consumers and external configuration rejection lived only in the analyzer. After: a single responsible contract layer supplies the candidate to all three consumers; admission validates settings before considering empty evidence. Reason/source: owner instruction to integrate into the whole structure, final audit evidence, and the existing STRUCTURAL_INTEGRATION invariant. Superseded duplicate checks and analyzer-only rejection are removed; no domain expansion or threshold changes.

Local engineering evidence: 69/69 tests, including changed settings, empty-evidence drift rejection, and refusal before registration/locked execution. The current freeze is `sha256:054864a6c2675610f23dfed718416109346dfd4f3bb47bf38c6323b3de321b86`. Previous main Run #200 passed all nine jobs, including private default-branch installation; [Run #203](https://github.com/ouroboros965018276-collab/universal-project-governance/actions/runs/37128361654) validates frozen revision `e3916a8aab43e23054127b65844916ce6aa50c8b` with nine successful jobs. Its Git commit time is `2026-10-03T14:04:22Z`; current acceptance observation is 2026-10-03T14:08:34.960184Z. Final promoted-main installation remains to be observed after merge. Git records this change's eventual source commit and commit time; neither is guessed here.

## Structure and bounded universal scope

Maintained-project/model/host-agnostic Skill; canonical semantics in `governance-src/`, deterministic compiler, generated `universal-project-governance/`, repository-only qualification. Bounds remain 16 policies, 8 Hot Path invariants, 102 Skill lines and at most two persistent owned project files. Unknown optional profiles fall back to universal rules. Existing Git/project truth supplies history; no parallel chronology database or additional profiles. Installed Codex runtime equals the generated candidate. Package SHA-256 remains `39d91d2f21cc390c08f4d630a64aca48134a4feddd604cc9d718f2a8d3cbf37e`.

## Previous changes and causal continuity

| Full source revision | Git time (UTC) | Function, reason and evidence |
|---|---|---|
| `b9bde7c20574c9e93cc983134c6c306ee29fba1e` | See Git commit | Close custom thresholds/protocol identity loophole found in final review; Run #197 nine jobs PASS. Its qualification fingerprint is superseded by the current contract integration. |
| `7547d96008a3081c5156210ab9f1f04c22c2bbce` | See Git commit | Record observed configuration acceptance; Run #199 nine jobs PASS. Merged as parent main `683b1ff0f85b36e9db38557d893051dcbc29ba50`; Run #200 nine jobs PASS. |
| `cf81a667722ce8edcfaec4c1dd07666b32e6a4e8` | 2026-10-03T13:21:13Z | Run #189 exposed Windows cp1252 Chinese JSON stdout failures. ASCII JSON transport preserves decoded Unicode; live freeze enforcement and regression added. Run #191 nine jobs PASS. |
| `31896578b73ae0207d2a1bf8d35ad8ff5608b4a7` | 2026-10-03T13:11:15Z | RC8 audit remediation at source/compiler/state/qualification layers; Run #189 seven jobs passed, two Windows jobs failed, repaired above. |
| `2127d022d3bb0db636324b0355ef307993486371` | 2026-10-03T11:07:15Z | Audited RC8 baseline; Windows 44/47 established repair rationale. Earlier squash implementation detail is not invented. |

RC8 documents stated checkpoints `2026-10-03T19:06:41+08:00` and `2026-10-03T18:54:06+08:00`; these are stated times, not independently observed code/commit times. RC9 active progress checkpoint was observed at `2026-10-03T12:51:59.340996Z`; original work-start is unknown. The readiness audit retains prior acceptance observations. Git preserves actual source commits and parents. Use causal references and monotonic ledger sequence for order; recording time is observation time.

## Handoff and next phase

Engineering CI passed. Verify actual promoted main, record exactly one completion report, and seal external stage acceptance; those post-promotion observations belong to the external stage report rather than being guessed before the commit exists. Next phase separately verifies real adapters, enforced isolation, independent model families, budgets and externally sealed preregistration/order before executing any round. Real results enter immutable `results/qN/` only after execution; no synthetic engineering fixture is efficacy evidence. Existing software/data tasks do not prove efficacy across every domain; generated handoff plans are same-family unless separately registered/reviewed.

After interruption, reconstruct from Git/current project truth, validation and active binding; unknown intent stays unknown. Export and verify evidence before epoch rotation. Inspect transient lock/temp residue before recovery. Preserve project-owned contracts and specialized workflows.
