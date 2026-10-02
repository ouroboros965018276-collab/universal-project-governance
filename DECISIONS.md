# Active Design Decisions

## Compiled governance is the canonical architecture
- **Status:** active
- **Decision:** Governance semantics are maintained as typed data and compiled into the installable Skill.
- **Why:** Capability growth must not linearly increase agent runtime cognitive load.
- **Consequences:** Generated runtime is never manually maintained; source/runtime drift is a release failure.
- **Applies to:** entire project.
- **Revisit when:** Agent Skills gains a native typed policy/runtime mechanism that supersedes this compiler.

## Typed Policy IR is data, not a DSL
- **Status:** active
- **Decision:** Policy IR uses finite JSON fields, stable IDs, enumerations, dependency references, evidence contracts, and schemas. It has no embedded conditions, loops, code, expressions, or plugin language.
- **Why:** Avoid creating a governance programming language that itself requires governance.
- **Consequences:** Complex decision logic belongs in deterministic compiler/runtime code, not policy syntax.
- **Revisit when:** a new requirement cannot be expressed without executable semantics; prefer compiler evolution before DSL expansion.

## One semantic rule has one canonical definition
- **Status:** active
- **Decision:** A rule is defined once in the canonical model and referenced by stable ID elsewhere.
- **Why:** Eliminate duplicated prose, drift, and contradictory definitions.
- **Consequences:** Profiles/tests/plans refer to IDs; they do not restate rule semantics.
- **Revisit when:** never, except if the canonical model itself is replaced by an equivalent single-source mechanism.

## Profiles activate; they do not redefine
- **Status:** active
- **Decision:** Project profiles only activate existing policy IDs.
- **Why:** Preserve project agnosticism without spawning per-domain governance forks.
- **Consequences:** data/ML/infra/etc. add context through activation, not duplicated rule sets.
- **Revisit when:** a domain proves to require genuinely new semantics, which must first become canonical policies.

## Risk-adaptive execution is based on observable facts
- **Status:** active
- **Decision:** Risk uses typed dimensions such as reversibility, security, data, external consumers, migration, contract change, unknowns, scope, and handoff. File/line counts are secondary heuristics.
- **Why:** Change size is a weak proxy for impact.
- **Consequences:** planner output controls report/handoff/evidence level; low-risk work remains lightweight.
- **Revisit when:** empirical agent evaluations justify better deterministic risk features.

## Governance state is schema-first
- **Status:** active
- **Decision:** Handoff, execution evidence, feedback, and release audit are canonical structured JSON state; Markdown is an optional rendered view.
- **Why:** Prevent template drift and support multiple future views (Markdown, IDE, API/MCP).
- **Consequences:** do not hand-maintain Markdown and JSON copies as parallel truth.
- **Revisit when:** a stronger portable structured format replaces JSON Schema.

## Complexity budgets are hard deterministic gates
- **Status:** active
- **Decision:** Runtime size, hot-path count, default policy closure, graph cycles/orphans/conflicts, and generated-runtime drift hard-fail CI.
- **Why:** Governance must prevent its own meta-complexity from becoming debt.
- **Consequences:** new capability must fit the budget, consolidate existing concepts, or explicitly revise the budget with evidence.
- **Revisit when:** empirical data supports a different budget.

## Semantic duplicate detection is advisory
- **Status:** active
- **Decision:** Deterministic structural duplicates can fail; fuzzy semantic similarity only warns.
- **Why:** Embedding/LLM similarity can produce false positives and should not block releases without human review.
- **Consequences:** future semantic fingerprints may improve advisory review but are not authority.
- **Revisit when:** deterministic semantic equivalence becomes reliable enough for a hard gate.

## Runtime integrity is tamper-evident, not authorization
- **Status:** active
- **Decision:** Generated runtime carries a SHA-256 manifest; repository permissions/VCS/CI/release artifact identity remain external trust anchors.
- **Why:** A writer can theoretically alter content and a local manifest together.
- **Consequences:** integrity claims remain bounded and technically accurate.
- **Revisit when:** signed artifact/attestation infrastructure becomes part of distribution.
