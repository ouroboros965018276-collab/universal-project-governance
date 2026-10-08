# Contributing

Current candidate: **3.0.0-rc.14 — Runtime Integrity and Diagnostic Hardening**. RC14 carries forward RC13 runtime completion and schema validation, then closes independent-review findings in credential redaction, timeout classification/budgets, and reporting opt-in failure atomicity. Qualification thresholds remain unchanged. Current test/freeze/smoke evidence and remaining host limits live in [`PROJECT_STATE.md`](PROJECT_STATE.md); historical outcomes and unknown causes remain unchanged.

## Structural contribution rule

Small isolated fixes may remain narrow. Non-trivial changes modify the responsible canonical module and clean the superseded in-scope path.

“Structural” never means “broaden scope.” Unrequested API/architecture redesign is a regression unless separately authorized.

## Runtime evolution

Edit `governance-src/`, regenerate runtime, run lint/integrity/tests, and regenerate test-freeze identity before empirical results begin.

Do not hand-edit generated runtime.

## Project lifecycle

Project ownership is limited to the paths declared in the canonical binding. New projects manage only `.governance/upg.json` by default; opted-in field testing adds the bounded report ledger. New persistent per-project files require an explicit architecture decision and complexity-budget change.

## Qualification changes

Protocol, fixtures, statistics, graders, mutations, adapters, runners, analyzer, deployment wrapper, canonical source, compiler, and generated runtime are frozen evidence surfaces.

After real testing starts, modifying any frozen surface invalidates the affected result round.

## Evidence rules

No result placeholders, threshold changes after seeing results, deterministic-failure relabeling, holdout leakage, raw secret-bearing traces, private chain-of-thought collection, or rewriting completed qN rounds.
