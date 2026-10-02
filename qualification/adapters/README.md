# Qualification Adapter Contract

Adapters connect the provider-neutral RC5 protocol to a real coding agent.

Required logical operations:

1. **prepare** — create a fresh isolated workspace and configure only the selected experimental arm.
2. **run** — execute one fresh-context task under the declared tool/time/context budget.
3. **collect** — return observable outcome metadata: exit state, usage, tool/event telemetry when available, and evidence references.

The qualification protocol never requires private chain-of-thought.

For locked holdout qualification an adapter must declare and externally enforce strong workspace isolation (`sandbox`, `container`, or `vm`). A plain local process adapter is development-only unless it is itself wrapped by a strong sandbox.

A2 must use a real host Skill installation/activation path. Merely concatenating SKILL.md into the prompt does not qualify as the Full UPG treatment unless the protocol explicitly records that host as a prompt-only Skill system.

Trigger qualification additionally requires observable activation telemetry. Handoff qualification requires a controlled checkpoint/continuation capability or an external harness that provides equivalent isolation.
