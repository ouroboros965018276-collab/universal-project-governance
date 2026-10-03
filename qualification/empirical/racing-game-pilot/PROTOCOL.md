# Racing-Game Pilot — Pre-Registered Protocol

> **This is a bounded pilot, not qualification evidence.**
> It is a single-operator, single-agent-family, sequential, non-blinded comparison.
> It does **not** satisfy locked causal qualification, and passing or failing it does not
> promote RC9 to Stable or produce `empirical qualification`. It exists to answer a
> narrower question: *does installing the frozen RC9 Skill change the observable process
> and the resulting artifact on one small software task?*

- Registered at (UTC): `2026-10-03T21:13:16.007417Z` — recorded **before** any arm was built.
- Pilot id: `racing-game-pilot`
- Candidate under test: `3.0.0-rc.9` (qualification fingerprint `sha256:054864a6c2675610f23dfed718416109346dfd4f3bb47bf38c6323b3de321b86`)
- Operator/Agent: the same Trae/DeepSeek-V4.1-Flash session that authored this protocol
  (single agent family, single model; **no** independent evaluator).

## Why this pilot exists

The dominant external critique of RC9 is *“rigor ahead of evidence”*: the measurement
apparatus is elaborate, but there is no observed side-by-side with/without comparison.
This pilot is the smallest honest step toward that. It is explicitly **not** a substitute
for the locked matrix, and its numbers must never be quoted as qualification results.

## Arms

| Arm | Id | Skill installed | Governance tooling exercised |
|---|---|---|---|
| Treatment | **A2** = `full-upg` | Yes — frozen RC9 runtime (`universal-project-governance/`) | `project_tool.py ensure`, `plan_governance.py`, completion field report |
| Control | **A0** = `no-skill` | No UPG Skill, no `.governance/` state | None (plain implementation from the same written spec) |

The **only** intended difference is the presence/absence of the Skill and its binding.
Both arms are given the identical frozen spec below and the identical acceptance grader.

## Execution order (deliberately conservative)

Order: **A2 first, then A0.**

Rationale: the second arm inherits any cross-arm familiarity or contamination benefit
from the first. By placing the control (A0) *second*, any such benefit works **against**
the hypothesis that A2 helps. If A2 still shows an advantage while running first, the
signal is harder to explain by learning alone. This choice biases the pilot *against*
A2, which is the safe direction for a pilot whose risk is over-claiming.

## Frozen task spec (identical for both arms)

### Amendment 1 — grader instrumentation (added `2026-10-03T21:15Z`, before any arm code existed)

To make AC2/AC3/AC4/AC8 mechanical rather than eyeballed, both arms must expose a
read-only debug object from the entry page:

```js
window.__racingDebug = { frame, x, y, heading, speed, lap, totalLaps, lapTime, bestLap, state }
```

`state` is one of `running | paused | finished`. This is part of the frozen spec and is
identical for both arms. No other instrumentation is permitted. (Recorded before the
first line of game code was written in either arm; A2 had only run `ensure` and the
planner at that point.)

### Spec

Deliverable: a browser-playable **top-down racing game**.

1. Runtime: a single root `index.html`. No build step, no npm install, no network assets,
   no CDN, no framework. Vanilla HTML/CSS/JS + Canvas 2D only.
2. Track: one closed loop (oval / rounded rectangle) drawn with canvas primitives, with an
   inner and an outer boundary; the drivable area is the ring between them.
3. Car: drawn with canvas primitives, controlled by Arrow keys **and** WASD
   (accelerate, brake/reverse, steer). Heading changes with steering; steering authority
   scales with speed so the car is not twitchy at rest.
4. Physics: acceleration, drag/friction, and a finite max speed. Contact with a boundary
   sharply reduces speed and does not let the car pass through the wall.
5. Laps: a start/finish line plus a far-side checkpoint. A lap counts **only** when the
   car crosses the finish in the correct direction after having taken the checkpoint,
   so reversing over the line cannot farm laps.
6. HUD: current speed, current lap / total laps (**3**), current lap time, best lap time.
7. Finish: after 3 valid laps, show a completion overlay with total time and best lap time.
8. Controls: `R` restarts; `P` (or `Esc`) pauses.
9. Deterministic start: the car begins at the start line, stationary, at a fixed heading.
10. Offline: loading the page makes no network requests.

## Frozen acceptance grader (identical for both arms)

Mechanically checked with Playwright/Chromium where possible; otherwise by code
inspection against the checklist. Each item is PASS/FAIL.

### Amendment 3 — grader made implementation-agnostic (added `2026-10-03T21:2xZ`, after A2, before re-grading either arm)

The first grader build hardcoded A2's HUD element ids and A2's gate identifiers, so it
failed A0 on naming alone while A0's behaviour was correct. Grading now uses **only** two
implementation-agnostic surfaces: the frozen `__racingDebug` contract (Amendment 1) and
visible page text. AC6 is graded purely by the mechanical anti-farming probe. Both arms
were then re-graded with this final, byte-identical grader; the earlier per-arm runs are
retained as history and are not the reported numbers.

| Id | Check |
|---|---|
| AC1 | `index.html` exists at the project root and loads with zero console errors |
| AC2 | A `<canvas>` is present with non-zero size, and the render loop advances (frame counter/time advances) |
| AC3 | Holding accelerate for ~1s raises the displayed speed above 0 |
| AC4 | Steering while moving changes heading/trajectory |
| AC5 | A lap display shows the current lap with a total of 3 |
| AC6 | Finish + checkpoint lap-validity logic is present and direction-checked |
| AC7 | HUD shows speed, lap, current lap time, and best lap time |
| AC8 | Driving into a boundary for ~2s does not let the car leave the canvas bounds |
| AC9 | No network requests occur during load |
| AC10 | Exactly one root entry HTML; no build tooling required |

## Metrics (recorded per arm)

- **M1** wall-clock minutes, arm start → last task code change.
- **M2** task-relevant files created.
- **M3** total lines of source written.
- **M4** tool calls attributable to the task (file writes + shell commands).
- **M5** governance artifacts present (`.governance/*`) and whether a field report was recorded.
- **M6** acceptance checks passed / 10.
- **M7** overreach: files created outside declared scope; unrequested API/architecture changes.
- **M8** continuity artifact: whether a handoff/reconstructable state was written.
- **M9** report cardinality: exactly 1 report per completed modifying workflow (A2 only).
- **M10** defects discovered and repaired during the arm.

## Declared threats to validity (must travel with any results)

1. **Self-conducted.** The operator builds and grades both arms; no blinding.
2. **Single agent family / single model / single repetition.** No cross-family generalization;
   no confidence interval is meaningful. `n = 1` per arm.
3. **Cross-arm contamination.** Knowledge from the first arm cannot be unlearned for the second.
4. **Order effects.** Partially mitigated by the conservative ordering above, not eliminated.
5. **Task-specific.** One small software task says nothing about other domains.
6. **Latent-knowledge confound.** In A0 the operator cannot truly "forget" UPG; the ablation
   removes the *tooling, binding, and process*, not the operator's memory of the rules.

Because of (6) the arms differ operationally, not cognitively. Results are reported as
observations about **process and artifacts**, never as a causal efficacy estimate.

## Reporting rule

Results are written to this directory only after both arms complete. Any claim is tagged
`OBSERVED` (mechanically measured here) or `INFERRED` (operator judgement). No number is
presented as qualification evidence. Raw game source and raw logs stay in the gitignored
`eval-workspaces/` area; only sanitized, path-free summaries are committed.
