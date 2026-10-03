# Threat Model — 3.0.0-rc.7

## Protected assets

Canonical governance semantics, generated Skill integrity, task scope boundaries, project binding ownership, field-test evidence, locked protocol/thresholds, holdout oracles, evaluator/runner/deployment identity, and immutable result rounds.

## Threats

### Structural overreach

**Risk:** an Agent interprets structural integration as permission to redesign unrelated modules or contracts.  
**Controls:** task-bounded scope guard, per-lab scope contract, changed-file/diff/API/architecture diagnostics, independent non-compensatory overreach gate.

### Correlated observations

**Risk:** pair-level IID resampling produces optimistic confidence intervals.  
**Control:** preregistered hierarchical Agent-family → scenario → repetition bootstrap.

### Aggregate benefit hides subgroup uncertainty

**Risk:** coverage and aggregate uplift are mistaken for significant benefit in each subgroup.  
**Control:** subgroup hierarchical CIs and explicit evidence-level semantics.

### Project-state proliferation

**Risk:** automatic governance creates accumulating report files.  
**Control:** exactly two managed files and one bounded rolling report ledger.

### Managed-state accidental cleanup

**Risk:** an Agent treats UPG binding/report state as junk.  
**Control:** generated Skill explicitly marks binding-owned paths as managed infrastructure; deployment gate detects their loss.

### Unsafe uninstall

**Risk:** automated removal deletes project-owned governance data or follows a symlink outside the project.  
**Control:** exact ownership validation, two-path removal allowlist, symlink refusal, empty-directory cleanup only.

### Field-report leakage

**Risk:** users share source/secrets through gray-test reports.  
**Control:** metadata-only contract, size bounds, common credential-marker rejection, review-before-sharing guidance, no private chain-of-thought.

### Benchmark leakage / frozen-evidence drift

**Control:** strong isolation, oracle exclusion, and a qualification fingerprint binding runtime, protocol, fixtures, evaluator, runner, and deployment wrapper.

### False zero-risk claim

**Control:** observed counts plus one-sided zero-event confidence bounds; zero observations never mean zero real risk.
