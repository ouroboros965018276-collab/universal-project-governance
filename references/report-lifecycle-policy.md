# Governance Report Lifecycle Policy

## Purpose

Prevent both missing engineering evidence and governance-generated technical debt.

## Report Levels

### Level 0: Change Note

Used for small scoped modifications.

Examples:
- typo fixes
- isolated bug fixes
- local refactoring

### Level 1: Engineering Report

Required for:
- multi-file refactoring
- architecture changes
- deletion of significant code
- API or schema changes
- security-sensitive changes

### Level 2: Audit Report

Required for:
- release candidates
- stable releases
- major governance upgrades

## Lifecycle Rules

| Category | Strategy |
|---|---|
| Current state | overwrite with latest truth |
| Change history | append |
| Release audit | immutable snapshot |
| Temporary reports | removable |

## Retention

Historical records should be periodically summarized and archived to avoid creating documentation debt.
