# Publishing and Release Gates

This repository publishes exactly one Skill: `universal-project-governance/`.

## Pre-release gate

A release candidate may be considered **pre-release ready** only when all of the following pass from the committed repository state:

- repository and Skill structural validation;
- security static audit;
- helper unit/integration tests on Python 3.8, 3.11, and 3.13;
- official `skills-ref==0.1.1` validation;
- deterministic package build;
- Skills CLI discovery and local installation;
- Skills CLI installation from the GitHub repository;
- self-governance docs validation;
- audit record updated with the exact commit and CI run.

## Stable gate

Stable promotion additionally requires empirical behavior evidence:

1. Run every query in `evals/trigger_set.json` multiple times in supported real-agent environments and measure false positives/false negatives.
2. Run every case in `evals/evals.json` in fresh contexts with this Skill and against a no-Skill or previous-stable baseline.
3. Grade each assertion with observable transcript/output evidence.
4. Review cost/latency/context overhead so governance quality is not purchased with unreasonable ceremony.
5. Critical failures must be zero: unsafe deletion, fabricated evidence/chronology, false debt-free/completion claims, source-of-truth duplication, namespace collision, or ignored validation failure.
6. Fix findings, increment RC if needed, and rerun the full deterministic and behavioral gate from a clean commit.

Static correctness and installability are **not** substitutes for behavioral effectiveness.

## Reproducible release artifact

```bash
python tools/package_release.py universal-project-governance --output-dir dist
```

The packager stages only the installable Skill, validates the staged bundle, normalizes ZIP metadata, and writes a SHA-256 checksum next to the archive.

## Candidate versioning

Use semantic prerelease identifiers (`2.0.0-rc.2`, `2.0.0-rc.3`, ...). Do not relabel an already-tested candidate after changing code or governance semantics; create a new candidate and rerun all gates.

## Public release

Before changing repository visibility to Public:

- verify repository history contains no private/legacy project material;
- verify no secrets or private URLs are present;
- enable private vulnerability reporting;
- ensure README, license, release version, package checksum, and Git tag agree;
- perform at least one clean public GitHub installation after visibility change before announcing stable.
