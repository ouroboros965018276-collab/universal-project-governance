# Threat Model — 3.0.0-rc.7

## Protected assets

Canonical governance semantics, generated Skill integrity, task scope boundaries, project binding ownership, field-test evidence, locked protocol/thresholds, holdout oracles, evaluator/runner/deployment identity, and immutable result rounds.

## Threats

### Structural overreach

**Risk:** an Agent interprets structural integration as permission to redesign unrelated modules or contracts.  
**Controls:** task-bounded scope guard, per-lab scope contract, changed-file/diff/API/architecture diagnostics, and independent non-compensatory `local_guard` / `structural_guard` exposure populations.

### Correlated observations

**Risk:** pair-level IID resampling produces optimistic confidence intervals.  
**Control:** preregistered hierarchical Agent-family → scenario → repetition bootstrap.

### Aggregate benefit hides subgroup uncertainty

**Risk:** coverage and aggregate uplift are mistaken for significant benefit in each subgroup.  
**Control:** subgroup hierarchical CIs and explicit evidence-level semantics.

### Project-state proliferation

**Risk:** automatic governance creates accumulating report files.  
**Control:** exactly two managed files while field reporting is enabled; disabling reporting reduces fresh binding to one managed file and creates no ledger.

### Managed-state accidental cleanup

**Risk:** an Agent treats UPG binding/report state as junk.  
**Control:** generated Skill explicitly marks binding-owned paths as managed infrastructure; deployment gate detects their loss.

### Reporting retirement data loss

**Risk:** Stable disables field reporting and silently deletes unexported gray-test evidence.  
**Control:** retirement of a non-empty existing ledger is rejected until explicit export/purge.

### Unsafe uninstall / failed install

**Risk:** automated lifecycle deletes project-owned governance data, follows a symlink outside the project, or leaves a fresh half-install.  
**Control:** exact ownership validation, managed-path removal, symlink refusal, empty-directory cleanup only, and best-effort rollback of newly created UPG-owned state plus newly installed Skill on fresh-install failure.

### Field-report leakage

**Risk:** users share source/secrets through gray-test reports.  
**Control:** metadata-only contract, size bounds, common credential-marker rejection, review-before-sharing guidance, no private chain-of-thought.

### Benchmark leakage / frozen-evidence drift

**Control:** strong isolation, oracle exclusion, and a qualification fingerprint binding runtime, protocol, fixtures, evaluator, runner, and deployment wrapper.

### False zero-risk claim

**Control:** observed counts plus one-sided zero-event confidence bounds; zero observations never mean zero real risk.
