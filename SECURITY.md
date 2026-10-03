# Security

Universal Project Governance inherits host Agent permissions. Repository provenance, generated runtime integrity, project binding ownership, adapter isolation, and evidence handling are trust boundaries.

## Runtime integrity

The Skill is compiler-generated and SHA-256 integrity checked. The manifest detects drift; Git/CI/release identity remains the external trust anchor.

## Project binding safety

UPG owns `.governance/upg.json` and, only while RC7 field reporting is enabled, `.governance/field-reports.json`.

Project lifecycle tooling refuses symlinked governance/managed paths, refuses removal of drifted/unowned binding state, writes managed JSON atomically, and preserves unrelated project governance files. Reporting retirement refuses to discard a non-empty ledger; failed fresh installs attempt owned-state rollback followed by Skill rollback.

## Field-report privacy

Reports are metadata/evidence summaries, not source archives. The tool enforces a total metadata size bound, per-entry length bound, and rejects common credential markers. These checks reduce accidental leakage but are not a complete secret scanner; users should review exports before sharing.

Private chain-of-thought is never required.

## Qualification isolation

Locked trials require sandbox/container/VM isolation and oracle exclusion. Other arms, previous answers, and hidden graders must not enter the tested workspace.

## Statistical integrity

Formal confidence claims use preregistered hierarchical inference. Safety denominators remain exposure-specific. Scope overreach uses separate local-guard and structural-guard exposure populations so one class cannot inflate confidence for the other.
