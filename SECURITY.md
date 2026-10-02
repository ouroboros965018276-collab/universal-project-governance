# Security

Universal Project Governance inherits host Agent permissions. Install only from trusted sources and review repository/release provenance before privileged use.

## Runtime

The Skill remains compiler-generated and SHA-256 integrity checked. The manifest is tamper-evident, not an authorization boundary; VCS/CI/release identity remains the external trust anchor.

## RC5 qualification security

Formal locked experiments require strong workspace isolation. A subprocess current directory alone is not sufficient holdout isolation.

Do not expose to an Agent under test locked oracle/expected-state files, hidden grader logic, other experimental-arm workspaces, or prior-trial reports/handoffs.

## Evidence privacy

Qualification does not require private chain-of-thought. Raw traces may contain repository source, paths, command output, credentials accidentally printed by tools, or provider metadata. Keep raw traces in controlled artifact storage by default. Commit only reviewed manifests, hashes, aggregates, and summaries.

Do not place secrets, credentials, raw private datasets, or unnecessary source contents into handoff/evaluation evidence.

## Adapter trust

Provider adapters and external harnesses are part of the qualification trust boundary. Record adapter/scaffold/model/environment identity in each formal qualification round.

Before public release, configure a documented private vulnerability-reporting channel.
