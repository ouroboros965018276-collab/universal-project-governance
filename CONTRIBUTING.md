# Contributing

RC5 is a qualification/freeze release, not a feature-growth release.

## Allowed contribution classes

- non-semantic qualification runner fixes;
- grader calibration and deterministic grader improvement;
- new provider/agent adapters;
- development eval expansion;
- additional executable fixtures that do not rewrite completed evidence;
- documentation corrections;
- real qualification evidence;
- security and compatibility fixes.

## Frozen behavior

Do not alter governance semantics, compiler contract, or runtime capability as an ordinary RC5 contribution.
A behavior-affecting change must explicitly invalidate the freeze, change the behavioral fingerprint, invalidate dependent qualification evidence, and trigger a new release decision.

## Qualification rules

- never put holdout oracle material into an Agent workspace;
- keep raw traces outside Git unless reviewed for sensitivity and size;
- deterministic failures cannot be manually relabeled as pass;
- do not move locked thresholds after seeing results;
- never overwrite a completed result round;
- do not create empty result placeholders;
- prefer thin external-harness adapters to rebuilding Agent orchestration infrastructure.
