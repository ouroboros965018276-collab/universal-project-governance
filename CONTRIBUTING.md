# Contributing

Current candidate: **3.0.0-rc.20.2 — Executable Git Checkpoints**. Change canonical source, regenerate the runtime, and keep engineering, bounded development measurements, independent efficacy evidence, and formal qualification distinct. Qualification thresholds remain unchanged; current evidence and remaining gaps are recorded in [PROJECT_STATE.md](PROJECT_STATE.md).

## Structural contribution rule

Small isolated fixes may remain narrow. Non-trivial changes modify the responsible canonical module and clean the superseded in-scope path.

“Structural” never means “broaden scope.” Unrequested API/architecture redesign is a regression unless separately authorized.

## Runtime evolution

Edit `governance-src/`, regenerate runtime, run lint/integrity/tests, and regenerate test-freeze identity before empirical results begin.

Do not hand-edit generated runtime.

## Project lifecycle

Project ownership is limited to the paths declared in the canonical binding. New projects manage only `.governance/upg.json` by default; opted-in field testing adds the bounded report ledger. New persistent per-project files require an explicit architecture decision and complexity-budget change.

Git checkpoint configuration and bounded recovery remain in the existing binding; native Git transactions use temporary Git-private paths. Preserve explicit opt-in and the allowlist when changing this integration. The [Git checkpoint contract](docs/git-checkpoints.md) describes lifecycle boundaries, deduplication and failure reporting; it adds neither a scheduler nor automatic remote writes.

## Qualification changes

Protocol, fixtures, statistics, graders, mutations, adapters, runners, analyzer, deployment wrapper, canonical source, compiler, and generated runtime are frozen evidence surfaces.

After real testing starts, modifying any frozen surface invalidates the affected result round.

Grader repairs must reject demonstrated false positives and accept legitimate task results. Never execute untrusted returned code to repair a scoring gap; use the bounded fixture contract or reviewed isolation. Labs exposed by diagnosis remain regression fixtures and cannot supply new independent holdout claims. Runtime text compression must preserve obligations and be assessed against actual task quality and metered cost; byte counts alone do not establish token or time savings.

## Evidence rules

No result placeholders, threshold changes after seeing results, deterministic-failure relabeling, holdout leakage, raw secret-bearing traces, private chain-of-thought collection, or rewriting completed qN rounds.
