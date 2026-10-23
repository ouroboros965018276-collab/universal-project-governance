# Contributing

Current candidate: **3.0.0-rc.20.9 — Scoped Engineering and Completion Review**. Change canonical source, regenerate the runtime, and keep engineering, bounded development measurements, independent efficacy evidence, and formal qualification distinct. Qualification thresholds remain unchanged; current evidence and remaining gaps are recorded in [PROJECT_STATE.md](PROJECT_STATE.md).

## Structural contribution rule

Small isolated fixes may remain narrow. Non-trivial changes modify the responsible canonical module and clean the superseded in-scope path.

“Structural” never means “broaden scope.” Unrequested API/architecture redesign is a regression unless separately authorized.

## Runtime evolution

Edit `governance-src/`, regenerate runtime, run lint/integrity/tests, and regenerate test-freeze identity before empirical results begin. The compiler stages a complete candidate before replacing an existing runtime, so failed generation retains the previous package.

Do not hand-edit generated runtime.

## Project lifecycle

Project ownership is limited to the paths declared in the canonical binding. New projects manage only `.governance/upg.json` by default; opted-in field testing adds the bounded report ledger. New persistent per-project files require an explicit architecture decision and complexity-budget change.

Git checkpoint configuration and bounded recovery remain in the existing binding; native Git transactions use temporary Git-private paths. Preserve explicit opt-in and the allowlist when changing this integration. The [Git checkpoint contract](docs/git-checkpoints.md) describes lifecycle boundaries, deduplication and failure reporting; it adds neither a scheduler nor automatic remote writes.

New normal completions require scoped review/audit evidence bound to current changed-file identities, including deletion and executable mode. See [completion input](docs/completion-review.md). Failed/stale review must leave the workflow unfinished; never retrofit successful reviews onto historical results.

## Qualification changes

Protocol, fixtures, statistics, graders, mutations, adapters, runners, actual arm-condition text, analyzer, deployment wrapper, canonical source, compiler, and generated runtime are frozen evidence surfaces.

After real testing starts, modifying any frozen surface invalidates the affected result round.

Grader repairs must reject demonstrated false positives and accept legitimate task results. Never execute untrusted returned code to repair a scoring gap; use the bounded fixture contract or reviewed isolation. Labs exposed by diagnosis remain regression fixtures and cannot supply new independent holdout claims. Runtime text compression must preserve obligations and be assessed against actual task quality and metered cost; byte counts alone do not establish token or time savings.

## Evidence rules

No result placeholders, threshold changes after seeing results, deterministic-failure relabeling, holdout leakage, raw secret-bearing traces, private chain-of-thought collection, or rewriting completed result rounds. Current documentation describes the live contract; [CHANGELOG.md](CHANGELOG.md) keeps only the latest and previous meaningful changes with observed dates and reasons. Earlier records remain in Git history.
