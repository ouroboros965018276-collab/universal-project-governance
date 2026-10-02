# Security

Universal Project Governance is an Agent Skill and inherits the host agent's permissions. Install Skills only from trusted sources and review repository/release provenance before use in privileged environments.

## RC4 security model

- the installable runtime is compiler-generated;
- its SHA-256 manifest detects accidental drift and partial mutation;
- compiler/runtime helpers use the Python standard library and do not require network access;
- governance evidence export selects only structured `.governance/` state, not arbitrary project source;
- policy IR is data and cannot execute embedded expressions/code;
- release trust additionally depends on VCS, CI provenance, repository controls, and artifact SHA-256.

The runtime integrity manifest is **tamper-evident, not tamper-proof**.

## Sensitive evidence

Do not place secrets, credentials, raw private data, or unnecessary source contents into governance handoff/execution/feedback/audit state. Evidence should identify checks and outcomes, not duplicate sensitive material.

## Vulnerability reporting

Before public release, configure GitHub private vulnerability reporting or another documented private security contact. Do not disclose exploitable vulnerabilities or credentials in public issues.
