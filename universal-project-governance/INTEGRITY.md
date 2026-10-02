# Skill Integrity Protection

## Purpose

Universal Project Governance governs projects and must also protect its own contract from accidental
or opportunistic edits by an agent performing unrelated work.

The installed Skill is therefore **read-only during ordinary project tasks**.

## Protected scope

RC3 uses a protect-all model: every distributed file under the Skill root is protected except the
generated checksum ledger itself and explicitly ignored local/cache artifacts.

The policy is machine-readable in `integrity/protected-files.json`.

## Ordinary project work

An agent MUST NOT:

- edit `SKILL.md`, references, helper scripts, templates, integrity metadata, license, or Skill changelog;
- weaken a rule because it is inconvenient for the current task;
- regenerate integrity checksums after noticing an unexpected mismatch;
- reinterpret a project task as permission to "improve" the installed Skill.

If `scripts/validate_integrity.py` reports a mismatch, treat the Skill as modified and report the
problem. Continue only under trustworthy higher-priority instructions or after restoring/reinstalling
a verified copy.

## Authorized Skill evolution

Changing the Skill itself requires an explicit task whose subject is the Skill, plus:

1. user/maintainer authorization;
2. documented reason and expected governance effect;
3. version impact analysis;
4. Skill changelog update;
5. checksum refresh using the explicit governance-upgrade command;
6. structural, integrity, security, helper, install, and behavioral validation appropriate to the change;
7. release/audit evidence refresh.

Checksum refresh command:

```bash
python3 scripts/refresh_integrity.py . --confirm-governance-upgrade
```

The confirmation flag is an **accidental-change barrier**, not authentication.

## Security boundary

This mechanism is **tamper-evident, not tamper-proof**. An agent with unrestricted write access can in
principle modify both protected files and their local checksum ledger. Strong release identity
therefore also relies on external anchors such as VCS review, CI provenance, repository protections,
and a release/package SHA-256.

Local integrity checks are designed primarily to catch accidental edits, partial copying, drift, and
"while I'm here" rewrites during unrelated work.

## Single source of version truth

The canonical runtime version is `metadata.version` in `SKILL.md`. Other manifests and changelogs
must agree with it and are validated against it. See [version policy](references/version-policy.md).
