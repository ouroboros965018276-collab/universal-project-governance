# Threat Model — 3.0.0-rc.6

## Protected assets

- canonical governance semantics;
- generated runtime integrity;
- structural-integration behavior;
- locked qualification protocol/thresholds;
- holdout oracles;
- safety exposure metadata;
- evaluator/runner identity;
- raw evidence and immutable result rounds.

## Threats and controls

### Patch accumulation

**Risk:** an Agent satisfies local metrics by adding wrappers, flags, fallbacks, duplicate configs, or parallel paths.  
**Control:** canonical `STRUCTURAL_INTEGRATION` policy + planner change mode + cleanup/evidence rules.

### Safety-denominator contamination

**Risk:** trigger/mutation/unrelated trials falsely increase safety confidence.  
**Control:** explicit per-trial `safety_exposures`; normal locked A2 behavioral/present-handoff rows only; class-specific denominators.

### Incomplete matrix promoted as Stable

**Risk:** a few easy scenarios or one dominant Agent family create apparent uplift.  
**Control:** 12 locked scenarios × 8 repetitions × complete A0/A1/A2 × each participating Agent family.

### Invalid attention control

**Risk:** A1 is much smaller than A2, making A2>A1 uninterpretable.  
**Control:** measured governance-context-token validity gate before uplift.

### Weak handoff metric

**Risk:** final task success hides regression of already-correct checkpoint state.  
**Control:** independent recovery and degradation-reduction gates.

### Governance artifact proliferation

**Risk:** the Skill creates persistent report/handoff debris per task.  
**Control:** runner-measured artifact count is a release efficiency criterion.

### Subgroup reversal

**Risk:** aggregate benefit hides severe harm to one Agent family or project profile.  
**Control:** subgroup minimum exposure and reversal floors.

### Benchmark leakage

**Risk:** Agent sees holdout oracle/graders.  
**Control:** strong sandboxing and oracle exclusion.

### Frozen-evidence drift

**Risk:** protocol/evaluator/runner changes without invalidating results.  
**Control:** qualification fingerprint binds the full evidence pipeline.

### False zero-risk claim

**Risk:** zero observed failures is reported as zero real risk.  
**Control:** per-class one-sided confidence upper bounds and explicit sample counts.
