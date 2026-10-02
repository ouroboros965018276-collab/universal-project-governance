# Threat Model — RC4 Compiled Governance

## Assets

- canonical governance model and schemas;
- compiler/static-analysis correctness;
- generated runtime identity;
- project governance state/evidence;
- release/audit provenance.

## Threats and controls

### T1 — Hand-edited generated runtime
**Risk:** source/runtime divergence or hidden weakening.  
**Controls:** compiler `--check`, generated-runtime integrity manifest, CODEOWNERS, CI.

### T2 — Policy graph corruption
**Risk:** missing dependencies, cycles, orphan rules, conflicting blocking obligations.  
**Controls:** deterministic Governance Linter hard failures.

### T3 — Governance meta-complexity
**Risk:** runtime/context size grows with every feature until agents stop following it.  
**Controls:** hard SKILL/hot-path/default-closure/Markdown budgets; source/runtime separation.

### T4 — DSL creep
**Risk:** Policy IR gains executable conditions/loops/plugins and becomes another programming language.  
**Controls:** finite schema fields and enums only; decision logic remains in compiler code.

### T5 — Integrity-manifest substitution
**Risk:** a privileged writer alters runtime and manifest together.  
**Controls:** do not claim local manifest as authorization; external VCS/CI/release digest anchors remain required.

### T6 — Evidence leakage
**Risk:** reports copy secrets/source/private data unnecessarily.  
**Controls:** schema-first minimal evidence; export tool selects governance-state files only; security guidance prohibits secret duplication.

### T7 — Over-governance
**Risk:** trivial work triggers large reports or unnecessary handoff artifacts.  
**Controls:** risk-adaptive planner; low-risk `none/change-note`; one current handoff/execution record; deterministic compaction.

### T8 — Semantic duplication
**Risk:** multiple policies restate the same intent under different IDs.  
**Controls:** one-definition rule; structural fingerprint advisory; human review for fuzzy semantic similarity until deterministic methods are trustworthy.
