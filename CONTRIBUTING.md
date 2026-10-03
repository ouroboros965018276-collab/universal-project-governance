# Contributing

RC6 is a structural-integration and qualification-correctness release.

## Change policy

Small, isolated, low-risk corrections may be narrow.

Non-trivial changes should be structural: integrate into the responsible canonical module, remove the superseded path, and update tests/docs/contracts in the same change. Avoid additive patch layers.

## Runtime evolution

Change `governance-src/`, not generated runtime. Regenerate the runtime, rerun complexity/static checks, regenerate qualification freeze identity when required, and preserve one canonical semantic definition.

## Qualification changes

Protocol, fixtures, evaluators, adapters, runners, and analyzer are frozen evidence surfaces after qualification freeze.

A change to one of those surfaces requires:

1. explicit reason;
2. updated qualification fingerprint;
3. invalidation/replacement of any dependent evidence round;
4. full deterministic validation before new Agent trials.

## Evidence rules

- no empty result placeholders;
- no moving locked thresholds after observing results;
- no deterministic failure relabeling;
- no holdout leakage;
- no raw secret-bearing traces in Git;
- no rewriting completed qN rounds.
