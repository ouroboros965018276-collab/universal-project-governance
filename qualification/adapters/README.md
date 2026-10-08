# Qualification Adapter Contract

Adapters connect the provider/host-neutral RC9 protocol to real Agents. They are qualification infrastructure, not part of the installable Skill.

## Required behavior

1. **Prepare** — use a fresh isolated workspace and configure only the selected experimental arm. Skill installation and A2 reporting opt-in happen before the measured task baseline; setup files are not charged as Agent-authored project changes.
2. **Run** — execute one fresh-context task under the declared Agent/model/scaffold/tool/budget condition.
3. **Collect** — return observable outcome metadata, usage, activation/checkpoint events, and evidence references.

Private chain-of-thought is never required or stored.

## Identity contract

Each adapter config declares:

- stable adapter `id`;
- Agent `family`, `model_id`, and `scaffold_version`;
- `host_tool.name` and `host_tool.version`;
- available `capabilities`;
- isolation mode;
- command/configuration;
- tool and budget profiles where applicable.

The runner derives SHA-256 identities for both the canonicalized adapter configuration and the adapter implementation/runtime. These hashes are written into locked trial evidence so a changed command/config/runtime cannot masquerade as the same experimental condition.

Adapters with helper scripts must list their paths in `adapter_runtime_files`; those bytes are included in the runtime identity. The runner expands `{python}` to its verified current interpreter when launching a helper, so Windows adapters do not depend on a separate `py` launcher. The bundled `codex_cli.py` helper installs a validated Skill under the host's project discovery path and invokes `codex exec` with workspace-write sandboxing and without user MCP/config overrides for development smoke. Its local process workspace is not externally attested isolation.

Public adapter summaries share redaction from `diagnostics.py`, including URL userinfo, tokens, secrets, and local paths. Raw stdout/stderr and partial preflight bytes remain local. The wrapper timeout reserves room for both Windows sandbox preflight and its own termination grace before assigning the remaining budget to the Agent call.

On Windows, use the native Codex executable supplied by the host (`CODEX_CLI_PATH`) rather than a `codex.cmd` shim. Declare required host process variables by name in `environment_passthrough`; their values are read from the invoking process at execution time and are not stored in adapter configuration. The Windows adapter passes only CLI/Codex-home identity, Windows profile/system paths, and configured proxy variables; it does not forward outer session/thread identifiers or shell-control flags. The helper reads only `windows.sandbox` and `features.respect_system_proxy` from `CODEX_HOME/config.toml`, then passes valid values as explicit overrides while retaining `--ignore-user-config` (so MCP, approval policy and unrelated user configuration stay isolated). Before any model call, `codex doctor --json` must confirm Windows sandbox provisioning; an unhealthy or unrecognized result fails fast with no model usage. The selected settings and preflight result are retained in trial events. Explicit `--sandbox workspace-write` remains in force. It never retries with full access or a weaker sandbox; a provisioning failure remains a host blocker.

For handoff trials, a separate `--continuation-adapter` may be supplied. Source and receiving identities are both recorded.

## Locked qualification

Formal locked trials require externally enforced `sandbox`, `container`, or `vm` isolation. A plain process working directory is development-only.

A2 must use a real host Skill installation/activation path. Trigger trials require `activation_trace`. Source-side handoff trials require `controlled_checkpoint`; the receiving adapter must support Skill injection.

## Measurement contract

Formal behavioral trials report:

- `total_tokens`;
- `wall_time_seconds`;
- `tool_calls`;
- `governance_context_tokens` for A1 and A2.

`governance_context_tokens` is governance/control instruction context added beyond the common task and shared scaffold. It is used only to validate that the attention-control arm is genuinely attention matched.

The runner computes persistent governance artifact counts from the final workspace rather than trusting Agent self-report.

## Events

Adapters may emit:

- `skill_activated`;
- `checkpoint_reached`;
- `critical_failures` — externally observed failure-class identifiers when the harness has direct evidence.

Deterministic repository checks remain authoritative over Agent self-description.

Locked adapter instances supply `isolation_attestation` with issuer, reference, and SHA-256 of an operator-reviewed external isolation record. The host must actually enforce mounts/network/credentials and oracle exclusion. Config booleans are insufficient; admission also matches the registered identity. Source handoff records model/scaffold and adapter runtime as well as config/host identity.
