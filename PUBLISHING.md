# Publishing and Release Gates

This repository publishes exactly one Skill: `universal-project-governance/`.

## Candidate identity and audit anchoring

Release evidence is anchored to the **candidate version + deterministic installable-package SHA-256 +
successful CI provenance for the release-relevant HEAD**.

The installed Skill additionally carries a protect-all SHA-256 integrity ledger. That ledger is local
tamper evidence; the deterministic package digest and repository/CI provenance remain external trust anchors.

Any change to installed Skill bytes, integrity policy, release tooling, tests/evals, security rules, or
release gates is release-relevant and requires a fresh full CI run.

## RC3 pre-release gate

A candidate is pre-release ready only when all applicable gates pass:

- Skill integrity ledger validation;
- Skill bundle and repository structure validation;
- security static audit;
- repository self-governance validation;
- integrated governance check;
- unit/integration tests on Python 3.8, 3.11, and 3.13;
- official `skills-ref==0.1.1` validation;
- deterministic package rebuild with identical SHA-256 across supported runtimes;
- Skills CLI discovery and local installation;
- integrity validation of the installed local copy;
- after merge to `main`: remote installation from the GitHub repository and installed-copy integrity validation;
- frozen RC audit synchronized with material findings/open blockers.

Branch CI intentionally does **not** claim to validate `owner/repo` remote installation, because that
form clones the repository default branch. Remote GitHub installation is authoritative only on `main`.

## Authorized integrity refresh

Checksum refresh is never a normal validation action. During an explicitly authorized Skill upgrade:

```bash
python universal-project-governance/scripts/refresh_integrity.py \
  universal-project-governance --confirm-governance-upgrade
```

After refresh, rerun all release-relevant gates. Do not auto-refresh after a mismatch.

## Stable gate

Stable promotion additionally requires empirical behavior evidence:

1. Run every query in `evals/trigger_set.json` repeatedly in supported real-agent environments and measure false positives/false negatives.
2. Run every case in `evals/evals.json` in fresh contexts with this Skill and against a no-Skill or previous-stable baseline.
3. Include cross-agent handoff scenarios: Agent A modifies/leaves state; Agent B continues using project state rather than hidden chat context.
4. Measure report-policy overhead so small changes do not generate disproportionate token/file cost.
5. Grade each assertion with observable transcript/output evidence.
6. Critical failures must be zero: unsafe deletion, fabricated evidence/chronology, false completion/debt-free claims, source-of-truth duplication, namespace collision, silent Skill mutation, or ignored validation failure.
7. Fix findings in a new RC and rerun deterministic + behavioral gates.

Static correctness and installability are **not** substitutes for behavioral effectiveness.

## Reproducible release artifact

```bash
python tools/package_release.py universal-project-governance --output-dir dist
```

The packager stages only the installable Skill, validates bundle structure **and the staged integrity
ledger**, normalizes ZIP metadata, then emits the archive SHA-256.

## Candidate versioning

Use semantic prerelease identifiers (`2.0.0-rc.3`, `2.0.0-rc.4`, ...). Do not relabel an already
tested candidate after changing release-relevant bytes or governance semantics.

## Public release

Before changing visibility to Public:

- verify history contains no private/legacy project material;
- verify no secrets/private URLs are present;
- enable private vulnerability reporting;
- ensure README, licenses, version, Skill integrity, package digest, and Git tag agree;
- perform a clean public GitHub installation and installed-copy integrity check;
- complete real-agent trigger/behavior/handoff qualification.
