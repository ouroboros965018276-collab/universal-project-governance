# Project State

## Purpose

Develop, validate, audit, and publish **Universal Project Governance**, one model-agnostic Agent Skill that keeps maintained-project changes coherent, current, evidenced, clean, and handoff-ready without letting governance complexity grow linearly with capability.

## Current state

The repository is validating **2.0.0-rc.4 — Compiled Governance Architecture**.

RC4 has replaced the RC3 document-heavy installable runtime with a generated runtime compiled from one canonical typed governance model. Stable/public release remains blocked until real-agent behavioral qualification is complete.

## Architecture / structure

- `governance-src/` — canonical governance source, schemas, profiles, runtime-script source, and presentation template.
- `compiler/` — deterministic source→runtime compiler.
- `universal-project-governance/` — generated installable Skill; never hand-maintained.
- `tools/` — repository validators, static analysis, security, and packaging.
- `tests/` / `evals/` — compiler/runtime/state/evaluation coverage.
- `audits/` — frozen or candidate release evidence.

## Canonical sources of truth

| Concern | Canonical source |
|---|---|
| Governance semantics | `governance-src/model/governance-model.json` |
| Project-type activation | `governance-src/profiles/*.json` |
| Structured state contracts | `governance-src/schemas/*.json` |
| Runtime presentation template | `governance-src/templates/SKILL.template.md` |
| Runtime helper source | `governance-src/runtime-scripts/` |
| Generated installable Skill | `universal-project-governance/` |
| Release gates | `PUBLISHING.md` |
| Current project state | `PROJECT_STATE.md` |
| Active design decisions | `DECISIONS.md` |

## Major capabilities

| Capability | Current implementation | Status |
|---|---|---|
| Core governance kernel | 7 hot-path invariants | RC4 |
| Typed Policy IR | canonical JSON model | RC4 |
| Rule graph | stable IDs + `requires` / conflicts | RC4 |
| Risk/context classification | typed task context + weighted risk vector | RC4 |
| Governance compiler | task-specific active closure + evidence/report/handoff output | RC4 |
| Capability profiles | activate existing policy IDs only | RC4 |
| Schema-first state | handoff/execution/feedback/audit JSON schemas | RC4 |
| Complexity gate | deterministic linter + CI hard limits | RC4 |
| Runtime integrity | compiler-generated SHA-256 manifest | RC4 |
| Evidence compaction/export | `state_tool.py` | RC4 |

## Constraints and invariants

- One semantic rule has one canonical definition.
- Governance profiles may activate but never redefine rules.
- The generated runtime is not manually edited.
- Runtime cognitive load is bounded by CI budgets.
- Deterministic structural defects hard-fail; semantic-similarity heuristics remain advisory.
- Current-state documentation describes current truth; release audits may remain historical/frozen.
- Stable release requires real-agent evidence beyond static correctness.

## Validation / operation

```bash
python compiler/compile_governance.py --check
python tools/governance_lint.py .
python tools/validate_repository.py .
python tools/validate_skill_bundle.py universal-project-governance
python universal-project-governance/scripts/validate_integrity.py universal-project-governance
python -m unittest discover -s tests -v
```

GitHub CI additionally covers supported Python runtimes, upstream Agent Skills validation, Skills CLI installation, and deterministic release packaging.

## Last meaningful change

- **When:** 2026-10-03
- **Change ID:** rc4-compiled-governance
- **Scope:** governance architecture, runtime distribution, validation, state/evidence contracts
- **Before:** RC3 required a 256-line runtime `SKILL.md`, a multi-document reference tree, Markdown templates, and agent-side composition of overlapping governance concepts.
- **What changed:** governance semantics moved into one typed canonical model; policy dependencies are compiled into task-specific plans; the installable runtime is generated and complexity-bounded.
- **Why:** prevent governance meta-complexity, semantic duplication, cognitive debt, and linear runtime-context growth.
- **After:** source complexity is absorbed by compiler/static analysis while runtime agent context remains bounded.
- **Impact:** major internal architecture replacement while preserving the original governance objectives.
- **Validation:** RC4 compiler/linter/tests/CI gates; final pre-release evidence is tracked in the RC4 audit.
- **Removed / superseded:** install-time reference-document tree, Markdown report templates, manual runtime policy synchronization.

## Previous meaningful change

- **When:** 2026-10-02
- **Change ID:** rc3-self-protecting-feedback-governance
- **Scope:** integrity, adaptive reporting, feedback, handoff
- **What / why:** added self-protection and proportional evidence feedback around the original governance lifecycle.
- **Validation:** RC3 main-branch CI and installability audit passed.

## Active exceptions

None in the RC4 implementation. Stable-release behavioral evidence remains a deliberate release gate, not hidden technical debt.
