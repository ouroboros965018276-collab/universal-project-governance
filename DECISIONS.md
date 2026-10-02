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

## Release evidence uses content identity, not self-referential audit commits
- **Status:** active
- **Decision:** Identify a release candidate by version, deterministic installable-package SHA-256, and successful CI for the current release-relevant HEAD. Audit Markdown records evidence but is not required to embed its own final commit SHA or post-commit run ID.
- **Why:** Requiring an audit document to contain the commit/run created after editing that same document creates an endless documentation-only commit loop without improving evidence quality.
- **Evidence / constraints:** The deterministic packager produces identical bytes across supported runtimes; GitHub preserves commit/run provenance independently of prose.
- **Consequences:** Release-relevant source or gate changes require a full rerun. Pure audit wording changes do not create a new candidate byte identity when the installable Skill is unchanged.
- **Applies to:** `PUBLISHING.md`, `audits/`, CI evidence, release promotion.
- **Revisit when:** Release attestation/provenance tooling provides a stronger immutable first-class mechanism.

## Installed Skill is protected by default
- **Status:** active
- **Decision:** Treat every distributed Skill file as read-only during ordinary project tasks. RC3 uses a protect-all SHA-256 ledger with explicit checksum refresh only during an authorized Skill-upgrade task.
- **Why:** Agents commonly optimize files they encounter; allowing an unrelated task to rewrite its own governance contract creates silent policy drift.
- **Evidence / constraints:** RC3 tamper tests detect protected-file edits and installed copies validate successfully after Skills CLI installation.
- **Consequences:** A checksum mismatch invalidates trust in the local Skill until restored/reinstalled or deliberately upgraded. The mechanism is tamper-evident, not cryptographic authorization against an actor with full write access.
- **Applies to:** all files distributed under `universal-project-governance/`.
- **Revisit when:** signed Skill packages or host-enforced read-only installations become broadly available.

## Reporting is adaptive, not mandatory bureaucracy
- **Status:** active
- **Decision:** Use minimal, standard, and evaluation observability modes. Trivial low-risk work does not create a standalone report by default; risk/scale/user intent can escalate to Engineering or Audit evidence.
- **Why:** Mandatory reports for tiny edits waste tokens and create file/history debt, while high-risk work and testing still need reviewable evidence.
- **Evidence / constraints:** RC3 report-classifier tests cover small changes, evaluation refactors, and releases.
- **Consequences:** Current truth and safety obligations never weaken, but evidence format scales with need.
- **Applies to:** consumer-project report generation and RC behavioral testing.
- **Revisit when:** empirical behavior evals show under-reporting or excessive ceremony.

## Handoff is current state; execution evidence is bounded
- **Status:** active
- **Decision:** Handoff Snapshot is overwritten at real continuation boundaries; Agent Execution Audits are generated only for evaluation/high-risk/explicit-audit cases and raw execution retention is bounded.
- **Why:** The next agent needs one current continuation state, not an archaeological pile of handoff files. Testing evidence must be retained long enough to review but not forever by default.
- **Evidence / constraints:** RC3 handoff and retention validators test empty snapshots and retention overflow.
- **Consequences:** Durable decisions/facts move into canonical project state; stale raw execution evidence can be summarized/archived and removed subject to project retention obligations.
- **Applies to:** `.governance/` observability and external audit workflow.
- **Revisit when:** project-specific compliance requires stricter retention.

