# 通用项目治理 | Universal Project Governance

**Universal Project Governance** is a model-agnostic Agent Skill for maintained-project governance.

Current candidate: **2.0.0-rc.4 — Compiled Governance Architecture**

RC4 replaces the RC3 document-heavy runtime with a compiled architecture:

```text
Canonical Governance Source
        ↓
Typed Policy IR
        ↓
Rule Graph + Static Analysis
        ↓
Risk-Adaptive Compiler
        ↓
Task-specific Governance Plan
        ↓
Bounded Runtime Skill
        ↓
Evidence / State / Handoff
```

## What changed in RC4

- one canonical machine-readable governance model;
- stable policy IDs and dependency graph;
- typed task context and governance-plan schemas;
- deterministic risk-adaptive plan compilation;
- schema-first handoff, execution, feedback, and audit state;
- generated installable runtime;
- hard complexity budgets in CI;
- static checks for duplicate IDs, missing dependencies, cycles, orphan rules, conflicts, missing evidence contracts, unknown profile activations, and runtime bloat;
- deterministic compaction/export helpers for governance evidence;
- integrity validation for generated runtime bytes.

The runtime `SKILL.md` is intentionally small and is generated from the canonical model. Do not maintain runtime policy prose by hand.

## Repository layout

```text
governance-src/                 # canonical governance source
├── model/
├── profiles/
├── schemas/
├── templates/
└── runtime-scripts/

compiler/
└── compile_governance.py       # source → installable runtime

universal-project-governance/   # generated installable Skill
├── SKILL.md
├── policy-index.json
├── schemas/
├── scripts/
└── integrity/

tools/
tests/
evals/
audits/
.github/
```

## Source of truth

Governance semantics live only in:

```text
governance-src/model/governance-model.json
```

Profiles may activate existing rule IDs but may not redefine them. Runtime Markdown is generated presentation, not a second semantic source.

## Install

For compatible Skills clients:

```bash
npx skills add ouroboros965018276-collab/universal-project-governance --skill universal-project-governance
```

The repository is currently private and RC4 is **not stable**.

## Maintainer validation

```bash
python compiler/compile_governance.py --check
python tools/governance_lint.py .
python tools/validate_repository.py .
python -m unittest discover -s tests -v
python tools/package_release.py universal-project-governance --output-dir dist
```

The GitHub workflow additionally validates Python 3.8 / 3.11 / 3.13, the upstream Agent Skills reference validator, Skills CLI discovery/install, runtime integrity, security, and deterministic packaging.

## Complexity policy

RC4 hard-fails when governance complexity exceeds declared budgets. Current key budgets include:

- runtime `SKILL.md`: ≤120 lines;
- hot-path invariants: ≤8;
- default active policy closure: ≤5;
- runtime Markdown files: ≤4;
- dependency cycles: 0;
- orphan policies: 0;
- conflicting blocking rules: 0.

Semantic-similarity duplicate detection remains advisory until it can be made deterministic enough for a hard release gate.

## Release state

Engineering/installability validation is required before RC promotion. Stable publication additionally requires real-agent trigger, behavior, cross-agent handoff, and overhead evidence.

See `PUBLISHING.md` and `audits/rc4-pre-release.audit.json`.

## License

Apache-2.0.
