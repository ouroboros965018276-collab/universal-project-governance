# RC19 bounded tool transport

The first eight development calls completed with known usage but no repository
tool calls or edits. They failed quality checks. Their CLI reported that Code
Mode was unavailable because its host was disabled. These observations remain
development costs; they are not independent acceptance results.

The replacement child profile sets `features.code_mode.enabled=false` and
`features.code_mode_host=true`. It retains `--ignore-user-config`, the read-only
native shell sandbox, disabled shell/web/apps/plugins/hooks/agent tools, and one
required MCP server with exactly five registered repository tools. It sets
`suppress_unstable_features_warning=true` to suppress the documented development
feature warning. Other CLI errors and unknown tool events still fail validation.

The installed CLI accepted the structured `features.code_mode.enabled=false`
key in a no-model `features list` check, reporting `code_mode=false` and
`code_mode_host=true`. The official [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
documents that key and `direct_only_tool_namespaces`. That reference does not
establish that the selected models can bypass the host. The local CLI exposes a
remote host option for app-server, not a verified equivalent in this exec profile.

The adapter requires the absolute installed sibling `code_mode_host_binary`.
Registration and the check immediately before dispatch hash that file, the CLI,
Python, Git, broker, adapter, schemas, and configuration. Where present, the
package manifest must identify the registered CLI and is hashed as well. These
are registered file identities. Actual CLI child process selection is explicitly
unattested in the capability; a declared hash alone does not prove which helper
process the operating system launched.

## Local host capability check

On 2026-10-12, a no-model probe directly launched the existing installed host
over stdio. It negotiated protocol version 1, opened a bounded V8 session, and
executed a fixed owner-written capability check with `enabled_tools=[]`.

| Check | Observed result |
| --- | --- |
| `process`, `require`, `Deno` | `undefined` |
| `fetch`, `XMLHttpRequest`, `WebSocket` | `undefined` |
| `import("node:fs")` | `unsupported import in exec` |
| Registered `tools` keys | Empty array |
| Unregistered tool call | Rejected as not a function |
| Host exit / stderr | 0 / empty |
| Model calls | 0 |

The probe did not attempt filesystem or network access. These selected runtime
observations support using the existing V8 host as the tool dispatcher. They are
not a complete security proof or evidence of OS/container isolation. The adapter
continues to require independently recorded broker calls and matching CLI tool
arguments, real edits, current validation/status evidence, and positive frozen
contracts. It does not execute model-written application code.

Owner-held raw IPC and the sanitized summary are retained under ignored
`eval-workspaces/rc19-code-mode-host-probe.raw.jsonl` and
`eval-workspaces/rc19-code-mode-host-probe.summary.json`. The raw journal contains
the exact sent/received JSON payloads; it is not a network wire capture.

| Artifact | SHA-256 |
| --- | --- |
| Installed host, package `0.162.0-alpha.20` | `f03190749208b5594fd5125d2d2b09e4ad00e2a1f74aeb11f60a6673dde83c43` |
| Installed package manifest | `7ccdf045d5cb1b0673662d8c0a03c9f335950052709fb250992953f2c861107c` |
| Raw local IPC journal | `2796a4a00473cdbdb92af6e287f6d0e14f4a2dc63881d39e62760943d642937a` |

No host configuration, authentication material, or installed executable was
modified. Positive end-to-end real tool execution must be established before
starting the independent campaign.
