# Contributing

Current candidate: **3.0.0-rc.12 — Qualification Evidence Refresh**. The historical eleventh RC12 development smoke failed at workspace routing. Prospective attempt 12 completed with zero tool calls and failed task/A2 checks under unrestricted host settings. Attempts 13/14 exited 1 before task evidence and did not retain exact stderr or usage, leaving causes unknown. See their separate summaries under `qualification/dev-smoke/`. Locked qualification still requires externally enforced isolation, reviewed attestation, and at least three actually usable independent Agent families.

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
