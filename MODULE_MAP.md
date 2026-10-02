# Module Map

## Frozen Governance Plane

- Location: governance-src/, compiler/, universal-project-governance/
- Status: RC5 behavior freeze
- Function: same compiled governance behavior validated in RC4, versioned as 2.0.0-rc.5.
- Invariant: no Policy/Hot Path/risk/handoff/report/compiler semantic delta from RC4.
- Validation: validate_freeze_delta.py, compiler drift, governance lint, integrity, multi-runtime package/install.

## RC5 Qualification Plane

- Location: qualification/
- Status: active infrastructure; real-Agent evidence pending
- Function: run/import controlled Agent experiments and convert observable outcomes into auditable PASS/FAIL/MORE_DATA evidence.
- Inputs: frozen runtime, executable fixtures, arm, Agent adapter, budgets.
- Outputs: immutable trial and aggregate evidence; no fake placeholders.
- Invariants: fresh paired trials; locked holdout data stays out of workspaces; deterministic failures dominate; no private chain-of-thought requirement; raw traces stay out of Git by default.

## Qualification Protocol

- Location: qualification/protocol/
- Status: locked before final qualification
- Function: preregister endpoints, thresholds, sampling, randomization, critical failures, grading authority, sandbox requirements, and stopping rules.
- Change safety: protocol changes alter the qualification fingerprint and require a new evidence round.

## Executable Labs

- Location: qualification/fixtures/
- Status: dev + locked holdout
- Coverage: 12 dev behavioral labs, 12 locked behavioral labs, handoff labs, 144 generated multilingual trigger cases.
- Invariant: oracle/check data is external to the Agent workspace.

## Agent Adapters

- Location: qualification/adapters/
- Status: provider-neutral contract + command adapter
- Function: connect real coding-agent harnesses to fresh isolated tasks and collect observable metadata.
- Invariant: formal locked runs require strong isolation; A2 requires Skill injection; trigger/handoff experiments require corresponding adapter capabilities.

## Mutation Evaluation

- Location: qualification/mutations/
- Status: active
- Function: build known-bad experimental policy variants and define repository defects to validate evaluator sensitivity.

## Statistical Analysis

- Location: qualification/analysis/ and qualification/analyze.py
- Status: active
- Function: paired deltas, bootstrap confidence intervals, exact discordance statistics, zero-event safety bounds, handoff uplift, trigger metrics, overhead ratios, and non-compensatory gate decisions.
- Output states: PASS / FAIL / MORE_DATA.

## Development Regression Assets

- Location: evals/, tests/
- Status: retained
- Function: fast deterministic regression coverage; not a substitute for locked real-Agent qualification.

## Release Evidence

- Location: audits/ and future qualification/results/qN/
- Status: candidate evidence
- Function: retain engineering/readiness audit and immutable generated qualification summaries.
