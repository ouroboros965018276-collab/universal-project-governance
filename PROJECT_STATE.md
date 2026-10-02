# Project State

## Purpose

Develop, qualify, and publish Universal Project Governance as a model-agnostic Agent Skill that improves maintained-project engineering behavior without allowing governance complexity or overhead to become a second technical-debt system.

## Current state

The repository is validating **2.0.0-rc.5 — Causal Qualification & Protocol Freeze**.

RC4 established the compiled governance runtime. RC5 intentionally freezes those semantics and adds a repository-only empirical qualification system. The project has not yet claimed real-agent behavioral improvement; that claim is blocked until locked qualification produces real evidence.

## Architecture

- governance-src/: canonical governance semantics; behavior frozen from RC4 except version identity.
- compiler/: deterministic source-to-runtime compiler; contract frozen.
- universal-project-governance/: generated installable runtime; normalized behavior must match RC4.
- qualification/: repository-only causal evaluation plane.
- tests/ and evals/: deterministic development/regression coverage.
- audits/: candidate and release evidence.

## Qualification capabilities

RC5 provides A0/A1/A2/K arms, fresh paired trials, executable dev/holdout labs, deterministic grading, normalized blind bundles, multilingual trigger cases, activation-trace contracts, controlled-checkpoint handoff contracts, policy/repository mutations, confidence analysis, overhead metrics, and immutable evidence-round rules.

## Identity and freeze

qualification/FREEZE.json is generated after the infrastructure stabilizes. It binds the behavioral fingerprint, qualification fingerprint, governance model, compiler, runtime, protocol, fixtures, graders, and adapter contract. A changed behavioral fingerprint invalidates prior qualification.

## Evidence state

Real Agent qualification results are pending. No empty result placeholders are accepted as evidence.

Final qualification has only PASS, FAIL, or MORE_DATA. No aggregate score can compensate for a critical failure.

## Last meaningful change

- When: 2026-10-03
- Change ID: rc5-causal-qualification-freeze
- Before: RC4 proved internal correctness, bounded complexity, installability, and deterministic behavior, but not causal benefit to real Agents.
- What changed: added a preregistered causal qualification plane while freezing runtime behavior.
- Why: distinguish 'the policy compiler works as designed' from 'the policy improves real engineering outcomes'.
- After: the repository can produce auditable counterfactual evidence for behavior, safety, handoff, triggering, and overhead.
- Validation: deterministic qualification infrastructure and final CI; real Agent qualification remains pending.

## Previous meaningful change

RC4 converted the document-heavy governance system into typed Policy IR + Rule Graph + Compiler + bounded runtime and passed engineering/installability gates.
