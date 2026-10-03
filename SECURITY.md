# Security

Universal Project Governance inherits host Agent permissions. Repository provenance, generated runtime integrity, project binding ownership, adapter isolation, and evidence handling are trust boundaries.

## Runtime integrity

The Skill is compiler-generated and SHA-256 integrity checked. The manifest detects drift; Git/CI/release identity remains the external trust anchor.

## Project binding safety

UPG owns only `.governance/upg.json` and `.governance/field-reports.json` during RC7.

Project lifecycle tooling refuses symlinked governance/managed paths, refuses removal of drifted/unowned binding state, writes managed JSON atomically, and preserves unrelated project governance files.

## Field-report privacy

Reports are metadata/evidence summaries, not source archives. The tool enforces a total metadata size bound, per-entry length bound, and rejects common credential markers. These checks reduce accidental leakage but are not a complete secret scanner; users should review exports before sharing.

Private chain-of-thought is never required.

## Qualification isolation

Locked trials require sandbox/container/VM isolation and oracle exclusion. Other arms, previous answers, and hidden graders must not enter the tested workspace.

## Statistical integrity

Formal confidence claims use preregistered hierarchical inference. Safety denominators remain exposure-specific. Structural overreach is measured independently so task success cannot hide scope abuse.
