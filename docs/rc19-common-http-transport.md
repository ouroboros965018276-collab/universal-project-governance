# Prospective common HTTP transport

RC19 development-v4 retained four strict quality failures containing TLS/stream
errors. Its eight reconnection errors and one HTTPS fallback message are new
observations; they do not identify the historical RC18 tail-pair cause. The v4
quality gate and charged usage remain unchanged.

New comparisons use the following child-process-only configuration in both
arms, with the existing official CLI and account connection:

```toml
model_provider = "upg_openai_http"
[model_providers.upg_openai_http]
name = "OpenAI"
wire_api = "responses"
requires_openai_auth = true
supports_websockets = false
```

There is no base URL, environment-key, token, auth object, header, query or
gateway override. No host configuration, permission selection or login material
is edited or copied. The bounded-tool adapter retains `never`, native read-only
sandboxing and its five explicitly preapproved broker tools. Both release arms
share this transport, and its effective configuration and source are hashed.

The installed CLI identifies itself as `0.162.0-alpha.20`. A read-only
`initialize`, `config/read`, `account/read(refreshToken=false)` check loaded the
selected custom provider and retained account type `chatgpt`, exiting zero with
empty stderr. That check performed no inference and cannot establish successful
HTTP inference, quality or efficiency.

Matching official source explains the supported route. The tagged
[provider implementation](https://github.com/openai/codex/blob/rust-v0.162.0-alpha.20/codex-rs/model-provider/src/provider.rs)
selects default routing from actual authentication mode, retains first-party
authentication and workspace routing with the exact `OpenAI` name and absent
base URL. The [auth implementation](https://github.com/openai/codex/blob/rust-v0.162.0-alpha.20/codex-rs/model-provider/src/auth.rs)
retains the caller's authentication manager when no override is supplied.
[Provider defaults](https://github.com/openai/codex/blob/rust-v0.162.0-alpha.20/codex-rs/model-provider-info/src/lib.rs)
and the [client](https://github.com/openai/codex/blob/rust-v0.162.0-alpha.20/codex-rs/core/src/client.rs)
implement the default ChatGPT route and HTTP dispatch when WebSocket support is
false. Tag object `7b4d251a7323044a8284e5158f5840af18b3306c` resolves to commit
`15c477d788a575de432f661def200ae7bc4a835e`. Version matching is not reproducible
build attestation of the installed binary.

This custom provider also differs from the built-in provider in metadata
defaults. It is a new common experimental scaffold, not an assertion that the
historical transport is byte-for-byte unchanged. Independent native comparisons
must instrument both historical and current callbacks with the same child
profile, disclose that instrumentation and measure its cost inside the callback.
The old callbacks and historical results are not patched or rebound.

The built-in `openai` ID cannot be overridden in this CLI; a local configuration
check rejected that candidate before inference. Removed WebSocket feature flags
are not used. New protocol/source identities and fresh artifact roots are
required before inference. Unknown calls, errors and uncertainty still fail
closed; transport fallback does not waive the frozen quality gate.
