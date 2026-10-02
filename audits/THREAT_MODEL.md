# Threat Model — RC5 Causal Qualification & Protocol Freeze

## Assets

Frozen governance semantics and behavioral fingerprint; qualification protocol/thresholds; locked holdout tasks/oracles; adapter/grader integrity; raw Agent traces; immutable result rounds.

## Threats and controls

### T1 — Runtime semantic drift during qualification
Control: RC4→RC5 freeze validator + behavioral fingerprint + generated runtime integrity.

### T2 — Benchmark leakage
Control: materialize only project fixture into Agent workspace; locked runs require external sandbox/container/VM isolation.

### T3 — Treatment leakage to blind judge
Control: normalized outcome bundles strip experimental arm and Agent identity where feasible.

### T4 — Evaluator blindness
Control: known-bad policy mutants and repository mutations must be detectable before qualification evidence is trusted.

### T5 — LLM judge overrides reality
Control: deterministic repository/executable evidence has higher authority and is non-overridable.

### T6 — p-hacking / moving gates
Control: locked protocol, preregistered endpoints, randomization, budgets and stopping rules are bound into qualification fingerprint.

### T7 — Raw evidence leakage / evidence debt
Control: raw traces ignored by default; controlled artifact storage; Git keeps hashes, aggregates and summaries.

### T8 — False zero-risk claim
Control: report sample size and confidence upper bound.

### T9 — Provider/time drift
Control: paired tasks, blocked randomization, temporal interleaving, recorded model/scaffold identity.

### T10 — Destructive over-governance
Control: CF10 critical-failure class and executable outcome checks.

### T11 — Result rewriting
Control: completed qN rounds are immutable; corrections invalidate and create qN+1.
