# Active Design Decisions

> Only decisions that still constrain the current project. Deep/superseded history belongs in Git.

## One Skill, progressive disclosure
- **Status:** active
- **Decision:** Maintenance, cleanup, technical-debt control, documentation truth, chronology, validation, and handoff remain one Skill. Detailed policy is split into references loaded on demand, not separate Skills.
- **Why:** These responsibilities must close together, while a monolithic always-loaded prompt wastes context and degrades routing efficiency.
- **Evidence / constraints:** Agent Skills supports a `SKILL.md` entry with supporting files; the candidate remains under the recommended compact entry-file size.
- **Consequences:** `SKILL.md` is the canonical router/contract; references may expand detail but may not weaken core invariants.
- **Applies to:** `universal-project-governance/`.
- **Revisit when:** The Agent Skills standard materially changes how supporting resources or activation are defined.

## Separate repository engineering from installed Skill
- **Status:** active
- **Decision:** CI, audits, tests, release packaging, and behavioral evals live at repository level; only the runtime Skill contract/resources/helpers live under `universal-project-governance/`.
- **Why:** Users should not receive repository-only maintenance machinery when installing the Skill, and the distribution boundary should be obvious.
- **Evidence / constraints:** Skills CLI supports selecting a named Skill directory from a repository.
- **Consequences:** Repository validation must verify the Skill directory is self-contained and licenses/version metadata remain synchronized.
- **Applies to:** repository layout and release pipeline.
- **Revisit when:** Distribution tooling requires a different canonical layout.

## Stable requires empirical behavior evidence
- **Status:** active
- **Decision:** Format validation, unit tests, and successful installation are necessary but insufficient for `stable`; trigger and behavior evals must be run in fresh real-agent contexts with evidence.
- **Why:** A structurally valid Skill can still over-trigger, under-trigger, add unnecessary ceremony, or fail to improve project behavior.
- **Evidence / constraints:** The repository contains explicit trigger and behavior eval sets; automated CI has no model credentials and therefore cannot honestly substitute for real-agent behavior tests.
- **Consequences:** Pre-release can be declared ready after deterministic gates pass, but stable remains blocked until behavioral evidence is recorded.
- **Applies to:** release promotion.
- **Revisit when:** A trustworthy, reproducible, credential-safe behavioral evaluation service becomes part of CI.

## Semantics over mandatory consumer filenames
- **Status:** active
- **Decision:** Consumer projects must preserve required governance semantics, but default files such as `PROJECT_STATE.md` or `MODULE_MAP.md` are bootstraps rather than mandatory names.
- **Why:** Forcing a second documentation system into a mature project would create the duplication this Skill is meant to remove.
- **Evidence / constraints:** Interoperability and one-source-of-truth invariants require reuse of existing canonical structures.
- **Consequences:** Validators for default templates are optional when a consumer uses equivalent canonical structures.
- **Applies to:** consumer project integration.
- **Revisit when:** A universal standard for project-state metadata becomes broadly adopted.
