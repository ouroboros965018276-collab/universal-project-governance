# Threat Model — 3.0.0-rc.9

## Protected assets

Canonical governance semantics, generated Skill integrity, task-scope boundaries, project-binding ownership, continuity state, field-test evidence, locked protocol/thresholds, holdout oracles, real execution identity, and immutable result rounds.

## Threats

### Abrupt interruption without handoff

**Risk:** quota exhaustion, crash, session loss, or tool failure ends work before the previous actor writes a formal handoff, and the next actor guesses state or intent.  
**Controls:** handoff-or-reconstruct continuity; receiver inspects canonical truth, observable work/VCS state, validation evidence, UPG state, and unresolved artifacts before modifying; unknown prior intent remains unknown; no chain-of-thought dependency.

### Legacy-project adoption damage

**Risk:** installing governance into an existing project rewrites structure, creates parallel truth, or requires a risky migration before governance can help.  
**Controls:** binding-v2 in-place adoption adds only UPG-owned state; existing content is preserved; current-task governance starts immediately; existing artifacts are treated as evidence rather than automatically authoritative design.

### Agent/vendor capability mismatch

**Risk:** instructions silently assume coding/CLI/browser/workspace capabilities that a different Agent class does not possess.  
**Controls:** capability handshake is observe-before-assume; behavior is capability-negotiated rather than vendor-whitelisted; unavailable validation is reported rather than fabricated.

### Experimental condition aliasing

**Risk:** two materially different adapter commands/configurations/host tools are labeled with the same scaffold version and analyzed as one condition.  
**Controls:** locked evidence binds adapter-config SHA-256, adapter-runtime SHA-256, host-tool name/version, model/scaffold/tool/budget identity; cross-Agent handoff binds both source and receiver.

### Sparse top-level inference

**Risk:** hierarchical bootstrap appears precise even though only a very small number of independent Agent-family clusters exist.  
**Controls:** locked matrix requires at least three Agent families; protocol states that bootstrap repetitions do not create top-level information; cross-family generalization remains separately and narrowly reported.

### Duplicate completion telemetry

**Risk:** a workflow writes multiple field reports while formal deployment validation checks only that some report exists.  
**Controls:** runtime reports count entries and the formal deployment gate requires exactly one report for a completed modifying workflow.

### Structural overreach

**Risk:** structural integration is interpreted as permission to redesign unrelated modules or contracts.  
**Controls:** task-bounded scope guard, per-lab scope contract, changed-file/diff/API/architecture diagnostics, and separate non-compensatory `local_guard` / `structural_guard` populations.

### Correlated observations

**Risk:** pair-level IID resampling produces optimistic confidence intervals.  
**Control:** preregistered hierarchical Agent-family → scenario → repetition bootstrap.

### Aggregate benefit hides subgroup uncertainty

**Risk:** aggregate uplift is mistaken for significant benefit in every subgroup.  
**Control:** subgroup hierarchical CIs plus evidence-level semantics separating positive subgroup evidence from severe-reversal control.

### Project-state proliferation

**Risk:** governance creates accumulating task/report files.  
**Control:** exactly two managed files while gray-test reporting is enabled; reporting retirement can reduce fresh binding to one file.

### Managed-state accidental cleanup

**Risk:** an actor treats UPG binding/report state as junk.  
**Control:** Skill marks owned paths as managed infrastructure; deployment validation detects their loss.

### Reporting-retirement data loss

**Risk:** a later runtime disables field reporting and silently deletes unexported gray-test evidence.  
**Control:** non-empty owned report evidence blocks silent retirement until explicit export/purge.

### Unsafe uninstall / failed install

**Risk:** lifecycle automation deletes project-owned data, follows symlinks, or leaves a half-install.  
**Control:** ownership validation, managed-path-only removal, symlink refusal, empty-directory cleanup only, and fresh-install rollback.

### Field-report leakage

**Risk:** report summaries include secrets or private data.  
**Controls:** metadata-only contract, 64 KiB bound, per-entry bounds, rejection of private-key/token/Bearer/JWT/assignment-style credential/database-URL patterns, and review-before-sharing guidance.

**Residual risk:** pattern matching is defense-in-depth and is not general-purpose DLP. Arbitrary PII, customer identifiers, internal hostnames, or novel secret formats may not be detectable without unacceptable false-positive/complexity cost. Gray testing must therefore treat report exports as reviewable sensitive metadata.

### Benchmark leakage / frozen-evidence drift

**Control:** strong isolation, oracle exclusion, and a qualification fingerprint binding runtime, protocol, fixtures, evaluator, runner/adapters, analyzer, and deployment wrapper.

### False zero-risk claim

**Control:** observed counts plus one-sided zero-event confidence bounds; zero observed events never mean zero real risk.

### RC9 evidence admission and chronology

**Controls:** registered task/round identity, strict supported schema constraints, frozen fixture exposure/cohort matching, retained artifact digest verification, observed critical-failure precedence, monotonic report sequence and causal parent references. Idempotent retries recover after the report was saved but its binding summary was interrupted. Old retries cannot rewind current truth. Unknown historical time or intent stays unknown.

**Trust limits:** isolation attestations, model/family declarations and preregistration require external operator verification; UPG cannot establish them from a self-declared boolean/hash. Local integrity manifests are not authorization signatures. The frozen locked matrix currently covers software/data behavior, not every runtime domain. The transient writer lock and atomic-write temp file may remain after abrupt process death: inspect current ledger/binding first, then explicitly recover only verified stale owned residue. Never infer that an old lock proves a live writer is absent. Explicit reporting epoch rotation bounds duplicate detection; preserve the verified export.
