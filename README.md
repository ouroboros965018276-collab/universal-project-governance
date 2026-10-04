# 通用项目治理 | Universal Project Governance

Current candidate: **3.0.0-rc.10 — Pilot Evidence and Usability Hardening**

Universal Project Governance is a model-agnostic, host-agnostic Agent Skill for maintained-project governance across software, data, infrastructure, research, content, product/specification, operations, design systems, automation, ML/AI, documentation, and mixed projects.

RC10 preserves RC9's bounded architecture, in-place adoption and capability-based interoperability. It absorbs a desensitized diagnostic racing-game pilot, closes the risk-key/report-obligation usability issues found there, and keeps formal qualification gates unchanged. It introduces no new domain profiles or policy expansion.

## What changes when installed

Without UPG, an Agent can still complete a task, but cleanup, current-truth updates, validation evidence, scope discipline and handoff recovery depend on the Agent remembering to do them. With UPG active on a maintained-project change, the Agent first observes available capabilities, chooses local or structural mode, keeps work inside the smallest responsible layer, removes replaced residue when safe, validates affected behavior, and records explicit unknowns instead of inventing history.

The generated plan now separates two concepts that were easy to confuse during field testing:

- `report` is the ordinary governance note level for the task.
- `field_report_obligation` says whether the temporary field-test ledger still requires exactly one completion report before claiming a modifying workflow complete.

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

RC10 is field-tested and engineering-validated, but not empirically qualified. Current local evidence includes real Agent field runs, current-version functional checks, and a diagnostic A0/A2 racing-game pilot where both arms passed the same 10/10 acceptance suite. That pilot produced useful feedback and no causal efficacy claim.

Formal dev-smoke, locked qualification, empirical qualification, and Stable remain blocked until immutable locked real-Agent evidence passes the current machine-frozen identity and protocol.

License: Apache-2.0.
