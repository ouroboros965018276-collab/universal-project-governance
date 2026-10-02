# Repository Instructions for AI / Agent Contributors

This repository dogfoods **Universal Project Governance**.

For every task that changes repository state, apply the governance semantics in
`universal-project-governance/SKILL.md` to this repository itself. In particular:

- preserve one installable Skill named `universal-project-governance`;
- do not duplicate canonical rules between repository docs and `SKILL.md`;
- keep `PROJECT_STATE.md`, `MODULE_MAP.md`, active `DECISIONS.md`, `CHANGELOG.md`, and validation evidence current when affected;
- remove superseded code/docs/tests/config in the affected scope rather than leaving parallel residue;
- never weaken evidence, safe-deletion, chronology, interoperability, or closure requirements merely to reduce test friction;
- do not promote a release candidate to stable without the release gates in `PUBLISHING.md`;
- treat `audits/` as evidence records, not as a second source of normative project truth;
- keep the installable Skill model/vendor agnostic; model-specific test harnesses belong outside the Skill directory.

`universal-project-governance/SKILL.md` is the canonical behavior contract for the distributed Skill.
Repository documents describe this repository's current development/release state.
