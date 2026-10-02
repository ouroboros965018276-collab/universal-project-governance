# 通用项目治理 | Universal Project Governance

Current candidate: **2.0.0-rc.5 — Causal Qualification & Protocol Freeze**

RC5 deliberately does not add new governance policy. RC4 established the compiled governance runtime; RC5 adds a repository-only empirical qualification plane that can prove or falsify whether the frozen runtime actually improves real coding agents.

## RC5 architecture

Frozen Governance Runtime → Real Agent + Real Task → Observable Repository Outcome → Qualification Plane.

The Qualification Plane covers paired counterfactual trials, no-Skill / attention-control / Full-UPG arms, targeted kernel/policy ablation, executable repository labs, trigger activation qualification, cross-agent handoff experiments, mutation-based evaluator sensitivity, deterministic and blinded grading, confidence intervals, and token/latency/tool overhead.

## Runtime freeze

Runtime behavior is frozen from RC4. The only governance-runtime change in RC5 is prerelease version identity. CI verifies a normalized behavioral fingerprint against the RC4 baseline commit.

The installable Skill remains bounded: 15 policies, 7 hot-path invariants, generated SKILL.md under the RC5 90-line freeze target, no runtime reference tree, and no new governance DSL.

## Experimental arms

- A0 — No Skill baseline.
- A1 — Attention Control: generic careful-engineering instructions to separate UPG benefit from generic extra attention.
- A2 — Full UPG: real host Skill treatment.
- K — Kernel Only: targeted diagnostic ablation, not a primary release arm.

Primary qualification uses fresh paired trials with the same task, fixture, model/agent scaffold, tools, and budgets. The experimental arm is the intended variable.

## Evidence authority

Deterministic repository/test evidence outranks semantic judgment. LLM judges are only for aspects that cannot be mechanically established, operate on de-identified outcome bundles, and cannot overrule deterministic failure. Human review is reserved for disagreements, critical cases, and release spot checks.

Private chain-of-thought is neither required nor part of the qualification contract.

## Executable qualification assets

- 12 development behavioral labs.
- 12 locked behavioral holdout labs.
- development and locked cross-agent handoff labs.
- 144 generated multilingual metamorphic trigger cases.
- policy mutants for Eval-the-Eval sensitivity testing.
- repository mutation categories for governance-behavior testing.

Locked holdout oracle material is never copied into an Agent workspace. Formal holdout runs require strong external sandbox/container/VM isolation.

## No magic score

RC5 uses non-compensatory gates: evaluator validity → critical safety → core-task non-inferiority → governance uplift → handoff uplift → trigger quality → efficiency → generalization. A severe failure cannot be averaged away by a better cleanup score.

## Results are evidence, not templates

There are intentionally no fake empty behavioral-results.json, handoff-results.json, or overhead-results.json files. Real qualification runs create immutable qN result rounds. Raw traces stay out of Git by default; Git keeps reviewed manifests, hashes, aggregates, and summaries.

## Current status

RC5 qualification infrastructure is under validation. The project is not yet empirically qualified and is not Stable. If locked qualification passes without changing the behavioral fingerprint, the intended next promotion is 2.0.0 Stable. If evidence exposes a core defect, Stable is blocked.

## Maintainer checks

    python compiler/compile_governance.py --check
    python tools/governance_lint.py .
    python tools/validate_freeze_delta.py
    python tools/validate_qualification.py .
    python tools/validate_repository.py .
    python -m unittest discover -s tests -v

License: Apache-2.0.
