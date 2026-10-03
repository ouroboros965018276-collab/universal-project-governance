# 通用项目治理 | Universal Project Governance

Current candidate: **3.0.0-rc.9 — Evidence and Continuity Hardening**

Universal Project Governance is a model-agnostic, host-agnostic Agent Skill for maintained-project governance. It is *designed* to apply across software, data, infrastructure, research, content, product/specification, operations, design systems, automation, ML/AI, documentation, and mixed projects.

**Design scope is wider than evidence scope.** Causal evidence to date comes only from bounded software micro-projects and software/data task matrices. Coverage of the other domains is design coverage, not demonstrated causal benefit. See [Current evidence status](#current-evidence-status).

RC9 preserves RC8's bounded architecture, in-place adoption and capability-based interoperability. It repairs evidence admission, portable freeze identity, invalid fixtures, critical-failure counting, chronology grading and workflow reporting. It introduces no new domain profiles or policy expansion.

## Quick start (5 minutes)

```bash
# 0. Prerequisites: Git, Node/npx (pinned skills@1.7.0), Python 3.8+
git clone https://github.com/ouroboros965018276-collab/universal-project-governance
cd universal-project-governance

# 1. Install into your own project (project-scoped)
python upg.py install --project /path/to/your/project --agent codex

# 2. Inspect the binding
python upg.py status --project /path/to/your/project

# 3. Uninstall (removes only UPG-owned paths)
python upg.py remove --project /path/to/your/project --agent codex --yes
```

Install writes only UPG-owned state: `.governance/upg.json` and, while field-test reporting is enabled, `.governance/field-reports.json`. A fresh-install failure rolls back both the binding and the Skill. Uninstall never touches unrelated project files, and pre-existing projects are adopted in place rather than restructured.

## What changes with the Skill (before / after)

Illustrative contract-level example — *not* measured output. Scenario: "the malformed-input path exits 1 but the docs say exit 2; also add a `--timeout` flag."

| | Without the Skill | With the Skill (A2) |
|---|---|---|
| Setup | Starts editing immediately from the chat prompt | Capability handshake, then a typed task context and a compiled plan (`change_mode`, explicit `scope_guard`) |
| Integration point | Fixes the observed symptom where seen | Integrates at the smallest responsible canonical layer; removes the superseded patch path in scope |
| Cleanup | Often skipped | Proportional cleanup is part of the change (invariant `PROPORTIONAL_CLEANUP`) |
| Evidence | "It works now" | Smallest sufficient checks tied to the actually tested revision (`VALIDATE_AFFECTED`) |
| Continuity | Next session re-derives state from chat | Project truth + observable work state reconstruct the situation; unknown intent stays unknown |
| Record | Ad-hoc commit | Exactly one bounded field-test report while `field_test_reporting=true` |

The point is not "more process". It is: the shape of the change, the cleanup, the evidence, and the recovered context are made explicit instead of left implicit.

## Cost

Governance is not free, and RC9 discloses its budget instead of hiding it:

- At most **2** UPG-managed project files; at most **1** task-governance report per completed modifying workflow.
- Qualification efficiency ceilings (acceptance limits, **not** observed measurements — no real locked round has measured them yet): median total-token ratio ≤ **1.35**, median wall-time ratio ≤ **1.5**, median tool-call ratio ≤ **1.35**, relative to the no-Skill arm.

An expensive governance Skill that pushes a project above those ceilings is treated as a failure of the Skill, not of the project.

## Architecture

```text
governance-src/                canonical governance semantics
        ↓ compiler/
universal-project-governance/  generated installable Skill
        ↓
project binding v2             .governance/upg.json
field-test ledger              .governance/field-reports.json
        ↓
human / coding / workspace / browser / tool-using Agent work
        ↓
qualification/                 repository-only causal qualification
```

Qualification code never ships as Agent runtime.

## Universal continuity

A planned unfinished transition should use one current handoff. RC9 does not assume that a previous actor had time to create one.

After quota exhaustion, crash, session loss, tool failure, or another abrupt stop, the next actor reconstructs before modifying: it reads current canonical project truth, observable worktree/VCS or equivalent state, existing validation/evidence, UPG state, and unresolved artifacts. Recovered facts are separated from possibilities; unavailable prior intent stays explicitly unknown. Recovery never requires private chat memory or chain-of-thought.

## Legacy projects: effective immediately

The first modifying activation runs the idempotent project `ensure` operation.

RC9 adopts pre-UPG projects **in place**. Installation adds only UPG-owned state and does not restructure, rewrite, or demand project-wide migration of existing content. Existing artifacts are evidence rather than automatically trusted design; governance applies to the current task immediately while preserving observed contracts and current canonical sources.

Owned field-test state remains bounded to:

- `.governance/upg.json`
- `.governance/field-reports.json`

An owned RC7 binding can upgrade to RC9 binding schema v2 without discarding its existing report ledger.

## Agent interoperability

RC9 does not maintain a vendor/model allowlist. Before modifying state, the Agent observes available capabilities such as filesystem, VCS, search, build/test, browser, application, or other tools, and governs with what actually exists.

The same contract therefore applies to conversational Agents, coding Agents, workspace/computer-use Agents, IDE/CLI Agents, and other tool-using systems. Missing capabilities reduce what can be verified; they never authorize fabricated validation.

## Project-type interoperability

Profiles are optional task hints, not mandatory project migrations. Current profiles cover software, data, infrastructure, ML/AI, automation, docs/knowledge, design systems, research/evidence, maintained content/editorial, product/specification, operations/runbooks, and mixed projects.

Unknown project types still receive the universal Hot Path and task/risk-triggered policies; no project is excluded merely because it lacks a named profile.

## Structural integration remains task-bounded

The planner returns `change_mode` and `scope_guard`.

- `local / local-only`: genuinely local low-risk work.
- `structural / task-bounded-responsible-layer`: non-trivial work changes the smallest responsible canonical layer and removes superseded in-scope patch paths.

Structural mode never grants permission for unrelated redesign, API/contract changes, architectural migration, or opportunistic refactoring.

## Automated lifecycle

```bash
python upg.py install --project /path/to/project --agent codex
python upg.py status --project /path/to/project
python upg.py export --project /path/to/project --output upg-field-test-reports.json
python upg.py remove --project /path/to/project --agent codex --yes
```

Install uses the pinned Skills CLI, validates the installed copy, and initializes/adopts the project binding. Fresh-install failure attempts owned-state and Skill rollback. Uninstall removes only UPG-owned paths and preserves unrelated project governance data.

## Gray-test report

While `field_test_reporting=true`, every completed modifying workflow must append **exactly one** bounded report. The qualification deployment gate verifies `report_count == 1`, not merely that a report exists.

This is the most invasive rule in the Skill, and it is deliberate: the RC9 test freeze requires the flag, so a standard RC9 install cannot opt out of it. It is bounded rather than open-ended — exactly one report per *completed modifying* workflow, one file, at most 200 entries, and no report at all for read-only work. Its measured cost at the smallest possible task size is recorded in the [racing-game pilot](qualification/empirical/racing-game-pilot/RESULTS.md): **7 extra governance tool calls (1 failed), 2 managed state files, ~73 s vs ~15 s code phase, for equal acceptance.** Treat that as the overhead floor, not a typical figure; if a real measurement ever shows this pushing a project past the efficiency ceilings in [Cost](#cost), that is a failure of the Skill, not of the project.

Reports contain metadata/evidence summaries rather than source bodies or private chain-of-thought. The ledger is one bounded file with at most 200 entries. Report validation rejects common private-key/token patterns, Bearer/JWT-like credentials, assignment-style secrets, and credential-bearing database URLs. This is defense-in-depth rather than a claim of general DLP; participants should still review exports before sharing.

## Qualification v3 / RC9 identity

Formal primary confidence intervals use hierarchical bootstrap:

```text
Agent family
  → scenario
    → repetition / pair
```

RC9 requires at least **3 Agent families** for the locked matrix. Bootstrap repetitions cannot create independent top-level information, so cross-family generalization is reported separately and remains deliberately narrower than within-family precision.

Locked evidence also binds the actual execution condition through:

- Agent family, model ID, scaffold version;
- adapter configuration SHA-256;
- adapter implementation/runtime SHA-256;
- host tool name/version;
- tool profile and budget profile;
- both source and receiving identities for cross-Agent handoff trials.

Release gates remain non-compensatory for coverage, deployment, evaluator/control validity, critical safety, structural overreach, task performance, governance uplift, handoff, trigger behavior, efficiency, and subgroup generalization.

## Current evidence status

Stages are kept strictly separate. **Having field-run evidence is not the same as being empirically qualified.**

| Evidence layer | RC9 status |
|---|---|
| Static / unit / CI engineering validation | ✅ Complete (69/69 local tests; CI 9/9 jobs) |
| Real-Agent field run *(informal, not formal dev smoke)* | ✅ Occurred — five host micro-projects plus a two-project reciprocal handoff exercise, with real problem discovery and repair |
| Real-project functional verification | ✅ Current five micro-projects: 5/5 functional PASS |
| Historical / original-workflow governance acceptance | ❌ 1 FAIL + 4 BLOCKED (retained, not rewritten) |
| Formal real-Agent dev smoke | ❌ Not executed |
| Locked causal qualification | ❌ Not executed |
| Empirical qualification | ❌ Not obtained |
| Stable | ❌ Not eligible |

The four named stages, in order:

0. **Field pilot (below qualification).** A bounded `A2` vs `A0` with/without comparison on
   one small task lives in
   [`qualification/empirical/racing-game-pilot/`](qualification/empirical/racing-game-pilot/RESULTS.md).
   It found **equal acceptance (10/10 both arms), better auditability for A2, and a real
   efficiency cost for A2**. It is a single-operator, `n=1` pilot and is **not** qualification.
1. **field-tested** — real Agents actually used the Skill on real work, and problems were found and repaired. **RC9 is here.**
2. **formal dev-smoke validated** — the frozen end-to-end experiment chain (adapter, isolation, registration, Agent execution, artifact retention, admission, analyzer) works. Passing dev smoke still does **not** show that A2 beats A0/A1. **Not yet run.**
3. **empirically qualified** — the preregistered A0/A1/A2 contrast over locked fixtures, frozen identity and thresholds actually passes on task performance, governance uplift, safety, handoff, overreach, efficiency and cross-Agent generalization. **Not obtained.**
4. **Stable** — released only after (3) passes under the machine-frozen RC9 identity. **Blocked.**

The candidate history is measurement-heavy, and that is a risk rather than a virtue. The documented `rc.7 → rc.8 → rc.9` sequence hardened hierarchical inference, continuity/adoption semantics and evidence admission — that is qualification *infrastructure*, not effect evidence. More measurement infrastructure cannot close the gap; only executing stage 3 can.

Compressed to one sentence: *Field-tested RC9; the current five micro-projects pass functionally, the original-workflow governance acceptance does not fully pass, and formal empirical qualification has not been obtained.*

This is **not** a randomized controlled trial, blind evaluation or locked qualification, and current functional PASS does not retroactively certify the missing historical evidence. Engineering validation does not itself prove causal benefit. Stable remains blocked until immutable locked real-Agent evidence passes the final RC9 machine-frozen identity and protocol.

License: Apache-2.0.
