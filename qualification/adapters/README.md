# Qualification Adapter Contract

Adapters connect the provider-neutral RC6 protocol to a real coding Agent. They are infrastructure, not part of the installable Skill.

## Required operations

1. **prepare** — create a fresh isolated workspace and configure only the selected experimental arm.
2. **run** — execute one fresh-context task under the declared model/scaffold/tool/budget profile.
3. **collect** — return observable outcome metadata, usage, activation/checkpoint events, and evidence references.

Private chain-of-thought is never required or stored.

## Locked qualification

Formal locked trials require externally enforced `sandbox`, `container`, or `vm` isolation. A plain process working directory is development-only.

A2 must use a real host Skill installation/activation path. Trigger trials require `activation_trace`. Handoff trials require `controlled_checkpoint`.

## Measurement contract

Formal behavioral trials must report these usage fields:

- `total_tokens`
- `wall_time_seconds`
- `tool_calls`
- `governance_context_tokens` for A1 and A2

`governance_context_tokens` means governance/control instruction context added beyond the common task and shared scaffold. It is used only to validate that the attention-control arm is actually attention matched.

The RC6 runner computes `persistent_governance_artifacts` directly from the final workspace; adapters must not self-report that value.

Formal adapter configs should also declare `tool_profile` and `budget_profile` so paired evidence cannot silently mix different execution budgets.

## Events

Adapters may emit:

- `skill_activated`
- `checkpoint_reached`
- `critical_failures` — externally observed CF identifiers when the harness has direct evidence

Deterministic repository checks remain authoritative over Agent self-description.
