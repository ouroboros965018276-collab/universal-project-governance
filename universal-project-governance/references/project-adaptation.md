# Project Adaptation

The governance semantics are project-agnostic. Adapt the evidence and validation mechanism to the
actual project rather than forcing software-only rituals.

## Software / services

Focus on source, interfaces, callers, tests, dependencies, configs, deployment, observability,
compatibility, and generated artifacts.

## Data / analytics

Distinguish source data, derived data, fixtures, caches, exports, and temporary artifacts. Track schema,
lineage, retention, quality checks, reproducibility, and consumers. Never delete data based only on a
code reference search.

## ML / AI

Distinguish data, prompts, preprocessing, model/config versions, evaluation sets, checkpoints,
artifacts, and serving contracts. Record reproducibility-critical versions and eval evidence. Do not
present a benchmark change as model-quality improvement without comparable evaluation.

## Infrastructure / platform

Treat desired state, runtime state, IaC, secrets/config, environments, rollout/rollback, dependencies,
and ownership boundaries as first-class. Never copy secrets into documentation or scan output.

## Documentation / policy / knowledge projects

"Behavior" means the meaning and downstream use of the documents. Remove superseded normative text,
keep one current policy, validate links/references/examples, and maintain decision/chronology where it
affects interpretation.

## Automation / workflows / prompts

Track triggers, inputs, tools/actions, permissions, side effects, outputs, failure modes, and consumers.
Remove obsolete branches and duplicated instructions. Verify the workflow rather than only syntax.

## Design systems / assets

Track canonical tokens/components/assets, generated derivatives, usage boundaries, deprecations, and
consumer migration. Avoid maintaining two manually editable versions of the same design truth.

## Hardware / mixed projects

Adapt "validation" to simulation, test fixtures, measurement, build artifacts, BOM/configuration,
interface contracts, calibration, or other domain evidence. Preserve safety and retention constraints.

## Monorepos / multi-project trees

Do not assume root configuration describes every package. Establish project/workspace boundaries and
apply cleanup/documentation/chronology at the smallest correct ownership scope, with root-level state
only for cross-cutting facts.

## Generated or vendor trees

Do not infer source conventions from `dist/`, `build/`, generated SDKs, vendored dependencies, caches,
or compiler output. Find the canonical source/generator first.

## Unfamiliar project type

Start from the universal questions:

- What is authoritative?
- What consumes this?
- What makes a change correct?
- What is generated/derived?
- What must be retained?
- What would make the next maintainer misinterpret the state?

Use those answers to choose project-specific checks without weakening the core invariants.
