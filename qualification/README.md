# Qualification Plane

Purpose: establish whether the frozen RC9 Skill causally improves maintained-project outcomes enough to justify its behavioral and operational cost.

This directory is repository-only and never ships as Agent runtime.

## Protocol q3

`protocol/qualification-v3.json` preregisters arms, sampling, hierarchical inference, safety exposure, deployment integrity, structural overreach, execution identity, efficiency, subgroup semantics, and stopping rules.

Development runs are diagnostic. Stable evidence uses locked trials only.

## Hierarchical inference

Formal paired effects use hierarchical bootstrap:

```text
agent_family
  → scenario_id
    → pair_id / repetition
```

RC9 requires at least three locked Agent families. Resampling 4,000 times cannot manufacture additional independent top-level clusters, so cross-family generalization is reported separately and is intentionally narrower than within-family precision.

## Reproducible execution identity

Locked behavioral evidence records:

- Agent family;
- model ID;
- scaffold version;
- adapter configuration SHA-256;
- adapter implementation/runtime SHA-256;
- host-tool name/version;
- tool profile;
- budget profile.

Cross-Agent handoff trials additionally record the source-side Agent family, adapter-config identity, and host-tool identity. Evidence produced under materially different adapter/host conditions cannot silently collapse into the same paired cell.

## Cross-Agent continuity

Handoff trials may use a different continuation adapter from the source adapter. This allows the qualification plane to test continuation across different Agent classes/vendors/hosts rather than only a second invocation of the same scaffold.

The runtime also supports abrupt no-handoff recovery through reconstruction. Qualification fixtures distinguish successful explicit handoff from ablated handoff and preserve observable task state so recovery/degradation can be measured without private reasoning.

## Generalization

Every Agent-family and project-profile subgroup reports task/governance CIs.

The gate distinguishes:

- `positive-subgroup-evidence`
- `severe-reversal-ruled-out-only`

Coverage/generalization does not automatically claim statistically significant benefit for every subgroup.

## Structural overreach

Behavioral labs define a scope contract. Locked A2 trials measure unexpected changed files, unrequested API/architecture changes, changed-file count, diff lines, and latency.

The overreach gate is independent from task success and has two non-pooled populations: `local_guard` detects unnecessary structuralization of local tasks; `structural_guard` detects structural work escaping its smallest justified canonical layer.

## Project deployment

A2 behavioral evidence includes RC9 binding-v2 validity and completion-report cardinality. A completed modifying workflow passes deployment integration only when exactly one report was recorded.

Fixed UPG managed files are counted separately from task governance artifacts.

## Trigger coverage

Trigger fixtures cover English and Chinese modifying/read-only contrasts across software, data, infrastructure, ML/AI, automation, docs, design systems, research, content, product, and operations objects. The trigger rule remains semantic: maintained-project state changes activate governance; read-only explanation/review does not.

## Results

Real result rounds appear under `results/qN/` only after execution and are immutable. No fabricated empty result artifacts are permitted.

## RC9 evidence admission

`round_manifest.py` registers a seeded, temporally interleaved paired matrix without executing an Agent. Locked runners require `--round-manifest` and `--trial-id`. The analyzer requires the same manifest, current fingerprints, schema-valid trials, frozen scenario/exposure IDs, unique IDs, strong-isolation operator attestations, and saved artifact identities. Invalid inputs fail before statistics; missing registered trials remain MORE_DATA. Existing thresholds are unchanged.

Before/after text snapshots and execution metadata are saved outside the Agent workspace before temporary cleanup; the analyzer reads the retained manifest and checks its digest and trial identity. Artifacts may contain sensitive test metadata; store privately and review before sharing. Hashes check supplied bytes, not a substitute for operator verification of the actual sandbox, family independence, execution order, and model versions. A declarative manifest cannot execute or enforce external isolation. Preserve the preregistration digest with an external timestamp/VCS authority before execution; a local editable JSON file is not that authority. Keep artifact paths available when analyzing an archived round.

The default round builder registers same-family source/receiver handoffs. A separately reviewed manifest can register cross-family source/receiver identities; do not describe the default plan as evidence for every cross-family pairing. Report absolute success for both present and ablated handoff conditions as well as their difference. The locked task matrix presently represents software/data tasks, so trigger breadth and universal runtime design do not establish causal benefit in research, content or other unmeasured domains. Three family clusters and trial-level zero-event bounds require cautious interpretation of independence.

No RC9 real-Agent round has run. This release phase contains engineering regression and installation acceptance only.

Production analysis also compares the supplied protocol and thresholds with the frozen candidate values. A copied identical configuration is accepted; changed settings, including relaxed gates or bootstrap counts, fail before inference. Engine unit tests explicitly mock this configuration boundary to keep synthetic bootstrap tests short and separately test rejection at the real entry point. This testing mock is absent from production CLI behavior.
