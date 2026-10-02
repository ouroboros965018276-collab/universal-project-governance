# Active Design Decisions

## RC5 freezes governance behavior

- Status: active
- Decision: RC5 changes prerelease version identity but does not add or alter governance semantics.
- Why: the remaining uncertainty is empirical effectiveness, not missing governance features.
- Consequence: CI compares RC5 normalized behavioral fingerprint against the RC4 baseline commit.

## Qualification Plane is repository-only

- Status: active
- Decision: RC5 experimental complexity lives under qualification/ and tools/tests; it does not ship in the Skill.
- Why: proving governance value must not increase runtime cognitive load.

## Primary comparison is paired counterfactual

- Status: active
- Decision: same task, fixture, agent, scaffold, tools and budget are paired across arms using fresh contexts.
- Why: unpaired tasks confound Skill effect with task difficulty.

## A0 / A1 / A2 with targeted K ablation

- Status: active
- Decision: primary arms are no-Skill, attention-control, and Full UPG. Kernel-only is diagnostic.
- Why: A1 separates governance benefit from generic extra attention; targeted K avoids combinatorial experiments.

## Outcome evidence outranks model self-description

- Status: active
- Decision: repository state, hidden tests, executable checks, and observable traces are primary evidence.
- Consequence: deterministic failure cannot be overruled by a semantic judge.

## Blind semantic grading is de-identified

- Status: active
- Decision: pairwise judges receive normalized outcomes without arm/model identity where feasible.
- Why: reduce treatment, provider, verbosity, and position bias.

## Critical failures are non-compensatory

- Status: active
- Decision: unsafe deletion, fabricated evidence/completion/chronology, duplicate truth, ignored validation, runtime self-modification, lost critical handoff risk, obsolete migration retention, and destructive over-governance are release blockers.

## No magic aggregate score

- Status: active
- Decision: qualification uses lexicographic gates: evaluator validity → safety → non-inferiority → uplift → handoff → trigger → efficiency → generalization.

## Zero observed failure is not zero risk

- Status: active
- Decision: safety reports sample size and confidence upper bounds.

## Holdout isolation is mandatory

- Status: active
- Decision: locked oracle/tests never enter an Agent workspace; formal holdout runs require external sandbox/container/VM isolation.

## Real result rounds are immutable

- Status: active
- Decision: q1/q2/... evidence is generated and never silently overwritten. Harness corrections invalidate and create a new round.

## Behavioral and qualification fingerprints are distinct

- Status: active
- Decision: behavioral fingerprint identifies runtime behavior; qualification fingerprint additionally binds protocol, fixtures, graders, and adapter contract.

## Provider-neutral protocol

- Status: active
- Decision: qualification is independent of any one Agent/eval harness. Thin adapters provide prepare/run/collect-equivalent behavior and declared capabilities.

## RC4 architectural decisions remain active

Compiled governance, typed non-executable Policy IR, one semantic rule/one definition, activation-only profiles, risk-adaptive execution, schema-first state, hard complexity budgets, advisory fuzzy semantic duplication, and tamper-evident runtime integrity remain unchanged.
