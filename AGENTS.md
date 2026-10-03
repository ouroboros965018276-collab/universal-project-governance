# AGENTS.md

## Project contract

Current candidate: **3.0.0-rc.6**.

### Default change mode

For a truly local low-risk correction, keep the change local and proportional.

For everything non-trivial, default to **structural integration**:

1. identify the responsible canonical layer;
2. change that layer instead of stacking a local workaround;
3. migrate affected consumers/contracts;
4. remove replaced shims, duplicate branches, stale docs, temporary files, compatibility paths, and obsolete artifacts when safe;
5. validate the resulting coherent structure.

Do not satisfy a task by adding another patch file, wrapper, fallback, feature flag, duplicate config, or parallel truth when the project can be cleanly integrated instead.

### Canonical source

Governance semantics live in `governance-src/`. The installable Skill is generated. Never hand-edit `universal-project-governance/` during normal work.

### Qualification

Qualification lives under `qualification/` and never ships in the Skill.

Formal locked trials must use fresh isolated workspaces. Never expose holdout oracle/check definitions or prior-arm results to the Agent under test.

Do not create result placeholders. Result files exist only after real evidence.

Do not request private chain-of-thought.

### Handoff

If work stops unfinished, persist current factual state, decisions, risks, validation entry points, and next safe action. Do not rely on chat memory.

### Current required checks

```bash
python compiler/compile_governance.py --check
python tools/governance_lint.py .
python tools/validate_qualification.py .
python tools/qualification_freeze.py . --check
python tools/validate_repository.py .
python -m unittest discover -s tests -v
```

If evidence contradicts a desired release outcome, evidence wins.
