# Security

Universal Project Governance inherits host Agent permissions. Treat repository provenance, Skill integrity, adapter execution, and qualification isolation as security boundaries.

## Runtime integrity

The installable runtime is compiler-generated and SHA-256 integrity checked. The manifest detects drift; it is not an authorization boundary. Git/CI/release identity remains the external trust anchor.

## Qualification isolation

Locked trials require externally enforced sandbox/container/VM isolation. A working-directory boundary is insufficient.

Never expose locked oracle/check definitions, other experimental arms, prior-trial answers, or hidden graders to the Agent under test.

## Safety measurement integrity

Critical-failure confidence is computed from explicit exposure populations. Do not add non-exposing trigger/mutation/ablation rows to safety denominators.

## Evidence privacy

Private chain-of-thought is not required.

Raw traces can contain source code, command output, paths, provider metadata, or accidental credentials. Keep raw traces in controlled artifact storage; commit only reviewed evidence needed for audit.

## Adapter trust

Record Agent family, model ID, scaffold version, tool profile, budget profile, isolation mode, and usage measurements for formal trials.
