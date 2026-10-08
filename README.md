# 通用项目治理 | Universal Project Governance

Current candidate: **3.0.0-rc.15 — Deterministic Skill Target Resolution**

Universal Project Governance is a model-agnostic, host-agnostic Agent Skill for maintained-project governance across software, data, infrastructure, research, content, product/specification, operations, design systems, automation, ML/AI, documentation, and mixed projects.

RC15 is an independent follow-up candidate for a verified installer defect: when projects contain duplicate UPG copies, the top-level installer could select a lexically earlier stale copy. Codex operations now resolve only the canonical `.agents/skills/universal-project-governance` target. Other Agent targets remain supported when unique and stop with an explicit ambiguity error when multiple copies exist. RC14 remains the frozen historical candidate; this repair receives a new version and qualification fingerprint. No qualification threshold is changed. See [`PROJECT_STATE.md`](PROJECT_STATE.md) for evidence and remaining host limits.

The prior frozen RC13 smoke passed registration, schema, artifact, and analyzer-boundary checks but failed closed before model invocation because Windows sandbox provisioning was incomplete; its sanitized record is [`qualification/dev-smoke/rc13-attempt-3.summary.json`](qualification/dev-smoke/rc13-attempt-3.summary.json). RC14 attempt 1 independently reproduced the same preflight blocker after current-freeze registration/schema/artifact checks; the adapter made no Agent call, and its sanitized summary is [`qualification/dev-smoke/rc14-attempt-1.summary.json`](qualification/dev-smoke/rc14-attempt-1.summary.json). The interrupted RC13 attempt has registration only, so invocation and usage remain unknown, not zero ([record](qualification/dev-smoke/rc13-attempt-2.summary.json)). Historical RC12 outcomes remain unchanged: 1 FAIL + 4 BLOCKED, and prospective attempts 13/14 keep their unknown causes. Locked qualification remains NOT RUN; empirical qualification and Stable remain NOT ACHIEVED because reviewed external isolation and three usable independent Agent families are not established.

## What changes when installed

Without UPG, an Agent can still complete a task, but cleanup, current-truth updates, validation evidence, scope discipline and handoff recovery depend on the Agent remembering to do them. With UPG active on a maintained-project change, the Agent first observes available capabilities, chooses local or structural mode, keeps work inside the smallest responsible layer, removes replaced residue when safe, validates affected behavior, and records explicit unknowns instead of inventing history.

The generated plan now separates two concepts that were easy to confuse during field testing:

- `report` is the ordinary governance note level for the task.
- `field_report_obligation` says whether the temporary field-test ledger still requires exactly one completion report before claiming a modifying workflow complete.

## Five-minute quickstart

From this repository, install the Skill into a maintained project and check its binding:

```bash
python upg.py install --project /path/to/project --agent codex
python upg.py status --project /path/to/project
```

Ask the Agent for one bounded change, for example: “Rename `--old-mode` to `--mode`; update its callers, tests, and current README; remove the old flag only after confirming no references remain.” UPG should inspect the project first, change only the canonical files and their tests/docs, run the affected checks, and leave unrelated files alone. The default install does not require a persistent field-test report.

For a gray test or qualification run that must retain one bounded report per completed modifying workflow, opt in explicitly:

```bash
python upg.py install --project /path/to/project --agent codex --field-test-reporting
```

The option is project-local. Existing opted-in bindings stay opted in and retain their report history; ordinary `ensure` does not silently disable them. This is an illustrative workflow, not a claim that every domain or Agent has been empirically validated.

### Concrete difference

Without UPG, an Agent might rename the flag in the CLI but miss a stale test or README reference. With UPG, it searches the affected project neighborhood, confirms the current contract, updates all in-scope references, runs the relevant test, and reports exactly what was and was not verified. The difference is a target behavior, not an observed success-rate claim.

## Architecture

```text
governance-src/                canonical governance semantics
        ↓ compiler/
universal-project-governance/  generated installable Skill
        ↓
project binding v2             .governance/upg.json
optional field-test ledger     .governance/field-reports.json
        ↓
human / coding / workspace / browser / tool-using Agent work
        ↓
qualification/                 repository-only causal qualification
```

Qualification code never ships as Agent runtime. The field-test ledger is created only for projects that opt in.

## Universal continuity

A planned unfinished transition should use one current handoff. RC9 does not assume that a previous actor had time to create one.

After quota exhaustion, crash, session loss, tool failure, or another abrupt stop, the next actor reconstructs before modifying: it reads current canonical project truth, observable worktree/VCS or equivalent state, existing validation/evidence, UPG state, and unresolved artifacts. Recovered facts are separated from possibilities; unavailable prior intent stays explicitly unknown. Recovery never requires private chat memory or chain-of-thought.

## Legacy projects: effective immediately

The first modifying activation runs the idempotent project `ensure` operation.

RC9 adopts pre-UPG projects **in place**. Installation adds only UPG-owned state and does not restructure, rewrite, or demand project-wide migration of existing content. New bindings default to reporting off; pre-existing opted-in state and its ledger are preserved. Existing artifacts are evidence rather than automatically trusted design; governance applies to the current task immediately while preserving observed contracts and current canonical sources.

Owned project state remains bounded to:

- `.governance/upg.json` (always)
- `.governance/field-reports.json` (only when reporting is enabled)

An owned RC7 binding can upgrade to binding schema v2 without discarding its existing report ledger.

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
python upg.py install --project /path/to/evaluation-project --agent codex --field-test-reporting
python upg.py export --project /path/to/project --output upg-field-test-reports.json
python upg.py remove --project /path/to/project --agent codex --yes
```

Install uses the pinned Skills CLI, validates the installed copy, and initializes/adopts the project binding. Fresh-install failure attempts owned-state and Skill rollback. Uninstall removes only UPG-owned paths and preserves unrelated project governance data.

## Gray-test report

Field-test reporting is off for new project bindings. While `field_test_reporting=true`, every completed modifying workflow must append **exactly one** bounded report. Use `--field-test-reporting` only for an explicitly opted-in field evaluation or qualification workspace. The qualification runner opts its A2 behavioral workspaces in; the deployment gate still verifies `report_count == 1`, not merely that a report exists.

Reports contain metadata/evidence summaries rather than source bodies or private chain-of-thought. The ledger is one bounded file with at most 200 entries. Report validation rejects common private-key/token patterns, Bearer/JWT-like credentials, assignment-style secrets, and credential-bearing database URLs. This is defense-in-depth rather than a claim of general DLP; participants should still review exports before sharing.

## Qualification v3 / frozen candidate identity

Formal primary confidence intervals use hierarchical bootstrap:

```text
Agent family
  → scenario
    → repetition / pair
```

The locked protocol requires at least **3 independent Agent families**. Bootstrap repetitions cannot create independent top-level information, so cross-family generalization is reported separately and remains deliberately narrower than within-family precision.

Locked evidence also binds the actual execution condition through:

- Agent family, model ID, scaffold version;
- adapter configuration SHA-256;
- adapter implementation/runtime SHA-256;
- host tool name/version;
- tool profile and budget profile;
- both source and receiving identities for cross-Agent handoff trials.

Release gates remain non-compensatory for coverage, deployment, evaluator/control validity, critical safety, structural overreach, task performance, governance uplift, handoff, trigger behavior, efficiency, and subgroup generalization.

## Evidence boundaries

Current UPG is field-tested and engineering-validated, but not empirically qualified. The TRAE diagnostic racing-game pilot built one A0 and one A2 game; both passed the same 10/10 mechanical acceptance suite. It exposed two usable improvements that were absorbed. Its retained aggregates include weak code-phase wall-clock observations (14.5s A0, 72.8s A2) and governance-call counts (0 A0, 7 A2, one failed); token totals were not instrumented. This was one family and one scenario, with no A1 arm, and was not locked. It therefore does **not** establish that UPG is more efficient, more professional, or causally better.

Profiles are routing hints and product support, not domain-by-domain effectiveness evidence. The locked task matrix currently covers software/data tasks; no causal benefit is claimed for research, content, operations, design, or other unmeasured domains.

Keep these stages separate:

- **Field-tested:** real Agents have used the Skill on actual tasks; observed defects can improve the product.
- **Formal dev-smoke:** the available host/adapter executes a registered development task end-to-end and retains reviewable evidence. This checks plumbing, not efficacy.
- **Locked qualification:** preregistered A0/A1/A2 trials use frozen identities, external isolation attestations, at least three independent Agent families, and immutable artifacts.
- **Empirical qualification:** locked evidence is admitted and all non-compensatory gates pass.
- **Stable:** release promotion follows only after the qualification contract is met.

**Qualification evidence boundary:** The RC9 field pilot retained weak single-family timing and governance-call aggregates for A0/A2; token totals were not instrumented, there was no A1 arm, and the observations cannot support a causal overhead estimate. RC12/RC13 smoke and micro-project outcomes remain historical diagnostics. RC14's local checks and smoke are recorded in [`PROJECT_STATE.md`](PROJECT_STATE.md). The frozen protocol still requires paired A0/A1/A2 evidence, non-compensatory safety gates, external isolation review, and three usable independent Agent families. Locked qualification is **NOT RUN**; empirical qualification and Stable remain **NOT ACHIEVED**. Development smoke is not release evidence.

License: Apache-2.0.
