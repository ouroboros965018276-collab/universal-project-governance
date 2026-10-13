# RC19 CLI transport and input-cost diagnosis

This is a source-backed diagnosis and an offline implementation check. It is
not a new model trial or a benefit result. Earlier protocols, raw receipts,
quality decisions and unknown-call fences remain unchanged. The incomplete v5
campaign must not be replayed automatically.

## Exact source and retry boundaries

The inspected official tag is `rust-v0.162.0-alpha.20`, annotated tag object
`7b4d251a7323044a8284e5158f5840af18b3306c`, resolving to commit
`15c477d788a575de432f661def200ae7bc4a835e`. The registered installed CLI SHA256 is
`bd970316b98c725f01cbfb92fdd3a952cb0e45425e15b7fb81d1927a60992f1a`.
Matching the declared version and public source tag is not a reproducible-build
attestation for that binary.

Both retry fields are optional unsigned integers. Their effective values have
an upper clamp of 100 and no positive lower clamp, so zero is accepted; the
defaults are four HTTP request retries and five stream retries.
[Provider fields and getters](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/model-provider-info/src/lib.rs#L180-L183),
[defaults](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/model-provider-info/src/lib.rs#L66-L75),
[effective values](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/model-provider-info/src/lib.rs#L498-L510).

The ordinary HTTP path is fully traced: provider conversion sets
`max_attempts` from `request_max_retries`; the API reexports the client provider;
`RetryConfig::to_policy` preserves that value; Responses uses EndpointSession;
the session calls its telemetry wrapper, which calls `run_with_retry`.
That loop starts at attempt zero and allows retries only before the maximum.
Consequently zero permits the initial send but no additional send through this
retry loop. [Provider conversion](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/model-provider-info/src/lib.rs#L454-L459),
[API alias](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/codex-api/src/provider.rs#L1-L2),
[policy conversion](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/codex-client/src/provider.rs#L18-L37),
[Responses endpoint](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/codex-api/src/endpoint/responses.rs#L135-L157),
[session send](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/codex-api/src/endpoint/session.rs#L139-L152),
[telemetry wrapper](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/codex-api/src/telemetry.rs#L68-L98),
[retry loop](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/codex-client/src/retry.rs#L84-L117).

The sampling loop reads `stream_max_retries`, but an earlier connection-failure
branch can bypass that limit when `unbounded_connection_retries` is enabled.
This stable feature defaults to true in the inspected tag. Two zero retry
fields alone therefore do not close the ordinary connection-retry path.
[Stream cap](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/core/src/session/turn.rs#L1629-L1636),
[connection bypass and bounded retry](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/core/src/responses_retry.rs#L87-L175),
[feature default](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/features/src/lib.rs#L1388-L1393).

The new shared child profile in `evolution/cli_transport.py` retains the existing
OpenAI Responses HTTP provider and adds all three settings:

```toml
model_providers.upg_openai_http.request_max_retries = 0
model_providers.upg_openai_http.stream_max_retries = 0
features.unbounded_connection_retries = false
```

Both arms use the same generator. ToolCodex binds its source, configuration and
generated overrides; native comparison preparation binds the same source in
the protocol, worker manifest and harness. Workers verify it before loading,
and actual native launches recheck source bytes. Actual argv reconstruction and
the existing read-only sandbox, global `never` approval, exact five broker
tools and scoped tool approvals remain enforced. No endpoint, authentication,
header or host-configuration override is introduced. Previous A_v1 preparation
and campaign records are not changed; a new campaign requires a fresh freeze.

This suppresses the identified ordinary transport retries. It does **not**
establish one provider request per CLI turn: the HTTP client has a separate
unauthorized-recovery loop, and successful tool use intentionally requires
multiple sampling responses. Authentication recovery can reissue a request
outside the ordinary retry policy. [HTTP recovery loop](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/core/src/client.rs#L1673-L1683),
[reissue after recovery](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/core/src/client.rs#L1795-L1821).

## Stream events, task quality and reported usage

An intermediate StreamError can describe a retry in progress. The app-server
marks it `will_retry=true`; terminal errors are marked false. The CLI JSONL
mapper emits a generic `error` and drops that structured retry marker. Thus
the string `Reconnecting...` plus a later completed turn does not itself prove
an incomplete final artifact, but it also cannot establish complete billing.
[Intermediate event mapping](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/app-server/src/bespoke_event_handling.rs#L1055-L1071),
[terminal event mapping](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/app-server/src/bespoke_event_handling.rs#L1628-L1636),
[CLI information loss](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/exec/src/event_processor_with_jsonl_output.rs#L447-L457).

The completed-turn JSONL usage copies the latest cumulative thread total.
The core records usage on upstream response completion; protocol documentation
distinguishes exact per-completion usage from accumulated/estimated/replayed
TokenCount events. These paths do not establish the billed cost of a failed
partial stream or an unsuccessful call without completion usage.
[Completed response accounting](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/core/src/session/turn.rs#L2949-L2985),
[cumulative CLI output](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/exec/src/event_processor_with_jsonl_output.rs#L118-L128),
[completion emission](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/exec/src/event_processor_with_jsonl_output.rs#L509-L556),
[usage boundary](https://github.com/openai/codex/blob/15c477d788a575de432f661def200ae7bc4a835e/codex-rs/protocol/src/protocol.rs#L1974-L1982).

The strict net-benefit gate continues to reject stream errors, fatal errors,
unknown usage and incomplete collection. Artifact checks and transport/accounting
admission can be reported separately; successful artifact checks do not waive
this gate. Known completed usage is retained, while a capacity failure without
usage stays unknown and fences replay. No string allowlist or retrospective
regrading is added.

## Historical input-cost measurements

The following counts use immutable v3/v4/v5 completed observations. Prompt and
broker journal hashes were checked against their receipts, and the five-tool
schema was reconstructed from each frozen Git revision and checked against its
registered schema hash. Bytes are UTF-8 counts, never token estimates. The v5
unknown seventh dispatch is excluded from numeric usage because its bill is
unknown, not zero.

| Development round | Completed turns | Reported input | Reported output | Cached input | Broker operations | Strict task passes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| v3 | 16 | 1,335,100 | 9,752 | 1,067,648 | 102 | 16 |
| v4 | 16 | 1,070,169 | 8,327 | 861,568 | 76 | 12 |
| v5, incomplete | 6 | 404,520 | 2,976 | 281,984 | 29 | 5 |

Across these records the broker schema is exactly 1,902 bytes. Supplied prompts
are 10,557–12,345 bytes: the Skill contributes 7,940–8,461 bytes, plans
1,482–3,125 bytes, and task text 201–320 bytes. Per-condition cached-input
fractions range from 64.52% to 82.25%. Cached input is already a subset of
reported input and must not be added again or treated as a dollar-price estimate.

In v4 the broker returned only 4,432 bytes of read file text across 16 turns;
1,628 bytes repeated a path already read in that call. The prompt and five
broker schemas alone cannot identify the model-visible framework schemas,
system prefix, request count or per-component token costs. Large cumulative
input and high cache fractions are consistent with repeated context across
sampling responses; this is an inference, not a causal attribution to one tool.
Cross-round totals are not a randomized performance comparison.

The smallest low-risk optimization target is fewer unnecessary sampling rounds:
batch the essential current-file reads, batch independent hash-bound patches,
and run the final validation/status evidence once the last patch is complete.
Keep stable instruction prefixes and compact plans, avoiding duplicate prose
while retaining the full applicable contract. Shortening a 1,902-byte schema or
removing 1,628 bytes of repeated file text alone cannot be credited with the
observed cumulative token changes. Keep tool argument schemas, hash
preconditions, read-before-patch evidence and final-state checks intact.

Offline checks passed: 36 adapter/broker tests, 29 native comparison tests,
and one additional completed-stream-error regression. The seven new regressions
cover shared-profile identity, drift/tamper rejection, worker binding, capacity
unknown fencing, and retention of known cost with strict stream-error failure.
These tests establish implementation behavior; future prospective model trials
must establish actual loading, failure rates, quality and net benefit under the
unchanged paired and joint-family criteria.
