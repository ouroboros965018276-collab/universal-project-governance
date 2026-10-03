# Racing-Game Pilot — Results

> **Not qualification evidence.** Single operator, single agent family, `n = 1` per arm,
> non-blinded, self-graded. Read together with `PROTOCOL.md`, including its declared
> threats to validity. Nothing here promotes RC9 toward Stable.

- Ran: `A2` (`full-upg`) then `A0` (`no-skill`), same frozen spec, identical final grader.
- Grader: `grader.py` (`sha256:d463c75f…d3d3`), applied byte-for-byte to both arms.
- Task: one offline top-down racing game, single root `index.html`, 10 acceptance checks.
- Raw evidence: [`artifacts/`](artifacts/) — both deliverables, both acceptance JSONs, the A2
  task context / field-report ledger / binding, with SHA-256 listed below.

## Headline

| | A2 — with UPG Skill | A0 — no Skill |
|---|---|---|
| Acceptance | **10 / 10** | **10 / 10** |
| Product files | 1 | 1 |
| Product lines | 392 | 253 |
| Governance inputs | 1 (`task-context.json`) | 0 |
| Managed state files | 2 (`.governance/upg.json`, `field-reports.json`) | 0 |
| Governance tool calls | 7 (1 failed) | 0 |
| Field report recorded | 1 (exactly one, as required) | 0 |
| Handoff written | no | no |
| Out-of-scope files | 0 | 0 |
| In-arm defects found | 2 | 0 |

Ordering was deliberately conservative: the control ran **second**, so any cross-arm
familiarity benefit works against the treatment.

## What the pilot observed

**1. Quality — no difference on this task (`OBSERVED`).** Both arms passed all ten
mechanical checks, including the strengthened anti-farming probe (cross the finish
forward without the checkpoint → reverse across it → forward again; the lap counter must
stay at 1). The two implementations are different code (392 vs 253 lines) but
behaviourally equivalent against the frozen acceptance surface.

**2. Professionalism / auditability — A2 clearly ahead (`OBSERVED`).** Only A2 produced:
an explicit `change_mode` + `scope_guard` from the planner, a declared active-rule
closure, an evidence list tied to the tested revision, and exactly one durable field
report satisfying the deployment-integration contract (`report_count == 1`). A0 left no
machine-checkable process record at all. On "can a third party audit what was decided and
why", A2 is materially better.

**3. Efficiency — A2 clearly behind on this task (`OBSERVED`).** A2 spent **7 extra
governance tool calls, one of them a failure**, plus a governance input file and two
managed state files, for a one-file task. The code phase took ~73 s vs ~15 s. This is the
cost the repo's own `efficiency` thresholds exist to bound, measured here at the cheapest
possible task size where the fixed overhead is least amortized.

**4. The LOC gap is not a Skill cost (`INFERRED`, and an important caveat).** A2's
`index.html` is +55% longer, but both files were authored by the same operator in the same
style family; the extra length is authoring verbosity (more comments and decomposition),
**not** something the Skill requires. It must not be reported as a governance overhead.

## Field defects found in the treatment arm

These are real product findings — the pilot's most useful output.

| Id | Finding | Impact | Proposed fix |
|---|---|---|---|
| **FD1** | The planner rejected `risk.data_impact`; the canonical keys are `data` and `handoff`. `SKILL.md` names the dimensions only in prose ("data impact", "handoff need"), and `task-context.schema.json` neither enumerates nor constrains risk keys, so the mismatch surfaces as a bare runtime error instead of an early, actionable validation error. | 1 wasted run + a debugging detour on the very first non-trivial task an adopter performs | State the exact key names in the Skill/template text, enumerate them in the schema, and make the planner error list the valid keys. |
| **FD2** | The plan reported `Report: none` while the binding's `field_test_reporting=true` still made exactly one field report mandatory. Two adjacent concepts, easy to conflate: "report level for this task" vs "deployment-gate reporting obligation". | Conceptual friction; a user could reasonably skip the report and then fail the deployment gate | Make the plan echo the outstanding field-report obligation explicitly when reporting is enabled. |

Both fixes touch frozen surfaces (`governance-src/` + generated runtime), so landing them
requires a deliberate version bump, re-freeze and new CI — **not** an in-place edit during
a pilot. They are recorded, not silently applied.

## Defects found in the experiment harness (not arm defects)

Recorded for honesty about the measurement apparatus:

1. **DOM-id coupling.** The first grader hardcoded A2's HUD element ids, so it crashed on
   A0. Fixed by grading through the frozen `__racingDebug` contract (Amendment 1).
2. **Identifier coupling.** AC6 additionally checked source identifiers (`START_GATE`),
   which failed A0's equivalent `FINISH` naming despite correct behaviour. Fixed by making
   AC6 purely behavioural (Amendment 3).
3. **Timing brittleness.** AC6's first version used fixed key-hold durations and never got
   the car back across the line. Fixed by polling to a position predicate.

Lesson for the real qualification plane: **the frozen surface must pin every interface the
grader reads.** Both coupling bugs came from grading something the spec never froze.

## Answers to the pilot's question

- *Is it more efficient?* **No — on this task it is measurably less efficient** (7 extra
  governance calls, 1 failed, two extra persistent files, ~5× code-phase wall clock).
- *Is it more professional?* **Yes — it is more auditable**: explicit scope guard, rule
  closure, evidence list, and a machine-verifiable completion record that A0 simply does
  not produce.
- *Is the output better?* **Not measurably, on this task.** Equal acceptance; the LOC
  difference is authoring style, not governance.

The honest summary: on a small one-file task the Skill buys **auditability at a real
efficiency cost**, and buys **no quality gain**. Whether that trade is worth it is exactly
what a locked, multi-task, multi-family round must decide — this pilot cannot.

## Archived artifacts (verification record)

The pilot's raw artifacts are archived under [`artifacts/`](artifacts/) so the record is
checkable instead of merely asserted. `artifacts/A2-full-upg/index.html` is the exact
revision named in the A2 field report's `result_revision`; re-running `grader.py` against
either archived `index.html` reproduces the corresponding archived acceptance JSON.

| Artifact | SHA-256 |
|---|---|
| `artifacts/A2-full-upg/index.html` | `7a48bdb2ab4aff6913c0c682448b2c828d19cf491f60fff0fe0dde97bb7ce29a` |
| `artifacts/A0-no-skill/index.html` | `2e271efef638e407e3c244e80d557cc80ef47f690b6cab075fc50c86bee82427` |
| `artifacts/A2-acceptance.json` | `c0d5f6bd61ff49d4ef0d76f60e90a322d09e3347310bbfc87ca0e38e4d5bbf45` |
| `artifacts/A0-acceptance.json` | `6ee995de8edc2c089248b5f87642b566412cee637af843bb5e2f4f98ee179d5b` |
| `artifacts/A2-task-context.json` | `f84c4e24b4f17f304b69c4cfa859dddda1710267ee2df751cf048b7c3dd67d6e` |
| `artifacts/A2-field-reports.json` | `c8adf8ee76832a06860a2adbeb0050cecf0ca31b88dc369136e93006448f9e00` |
| `artifacts/A2-binding.json` | `8fd1ad4970391f75352ff5e542321c7c2cb847d0bedc6a69c45d8da49edfe3d6` |
| `grader.py` | `d463c75fbb3913679487c7b846af69ec2bf9e4366c15a66ad135f5cd7055d3d3` |

Hashes are of the archived bytes, so they can be recomputed directly from a checkout. The two
`index.html` deliverables — the ones that carry the recorded `result_revision` — are
byte-identical to their run-time bytes; the archived JSON companions were line-ending
normalized to LF by the repository's `* text=auto eol=lf` attribute, which changes their byte
hash but not their parsed content.

These are sanitized, immutable copies of the run outputs. The live authoring workspace stays
outside release source (`.gitignore` excludes `eval-workspaces/`), and each file was checked
to contain no local absolute paths, credentials or operator identifiers beyond the disclosed
Agent family.

## What this does NOT show

- Not a causal efficacy estimate; not a confidence interval; not generalization.
- Not evidence for any other project type or task size.
- Not `empirical qualification`, and not an input to promoting `Stable`.
- A0's operator could not "unlearn" UPG (protocol threat 6): the ablation removed the
  tooling, binding and process, not the operator's knowledge.
