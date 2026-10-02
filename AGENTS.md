# Repository Instructions for AI / Agent Contributors

This repository dogfoods **Universal Project Governance**.

For every task that changes repository state, apply the governance semantics in
`universal-project-governance/SKILL.md` to this repository itself.

## Protected Skill rule

The distributed Skill is protected. During ordinary repository work, do **not** edit files under
`universal-project-governance/` unless the user/task explicitly authorizes a Skill upgrade or repair.

If protected Skill files change:

1. explain why the change is a governance change, not incidental cleanup;
2. update version/changelog/evals as required;
3. refresh checksums only with the explicit governance-upgrade command;
4. rerun integrity, security, runtime, package, official-spec, and installation gates.

Never refresh checksums merely to make an unexpected integrity failure disappear.

## Repository governance

- preserve one installable Skill named `universal-project-governance`;
- do not duplicate canonical rules between repository docs and `SKILL.md`;
- keep `PROJECT_STATE.md`, `MODULE_MAP.md`, active `DECISIONS.md`, `CHANGELOG.md`, and validation evidence current when affected;
- remove superseded code/docs/tests/config in scope rather than leaving parallel residue;
- never weaken evidence, safe-deletion, chronology, interoperability, integrity, or closure requirements to reduce test friction;
- use proportional reporting: small edits should not create report bureaucracy;
- treat `audits/` as frozen release evidence, not a second source of current truth;
- keep model-specific evaluation harnesses outside the distributed Skill;
- do not promote a release candidate to stable without the gates in `PUBLISHING.md`.

`universal-project-governance/SKILL.md` is the canonical behavior contract for the distributed Skill.
Repository documents describe this repository's current development/release state.
