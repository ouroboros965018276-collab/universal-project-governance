# Changelog

## 3.0.0-rc.6 — 2026-10-03

Structural Integration & Qualification Hardening.

- Adds canonical `STRUCTURAL_INTEGRATION` semantics and planner `change_mode = local | structural`.
- Makes medium/high-risk and intrinsically structural operations default to canonical-layer integration instead of patch stacking.
- Rebuilds qualification analysis into independent coverage, control-validity, safety, handoff, efficiency, and generalization gates.
- Replaces one global critical-failure denominator with per-class explicit exposure populations.
- Requires 12 locked behavioral scenarios, 8 complete repetitions per scenario × Agent-family cell, complete A0/A1/A2 arms, and balanced Agent-family coverage.
- Strengthens subgroup generalization with minimum complete-pair exposure and severe-reversal checks.
- Enforces both handoff recovery uplift and handoff degradation reduction.
- Enforces persistent governance artifact overhead.
- Enforces A1/A2 governance-context token matching before governance-uplift claims.
- Keeps 5 repetitions as a development checkpoint; Stable requires at least 8 locked repetitions per cell.
- Expands the qualification fingerprint to bind the full evaluator and runner pipeline.
- Removes RC-version-named tests/evals, RC3/RC4/RC5 prerelease audit files, obsolete prompt-only eval layers, the RC5 protocol file, and the RC4→RC5 freeze-delta helper from the current tree.

## 2.0.0-rc.5 — previous meaningful state

RC5 froze the compiled runtime and introduced the repository-only causal Qualification Plane with A0/A1/A2/K arms, executable labs, trigger experiments, handoff experiments, mutation evaluation, and machine fingerprints. RC6 keeps that concept but fixes the statistical and structural enforcement gaps found before real locked qualification.
