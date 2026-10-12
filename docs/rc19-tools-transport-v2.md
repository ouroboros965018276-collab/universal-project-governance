# RC19 transport probe v2: host observed, MCP calls rejected

The two registered development turns completed with known usage and passed
independent evidence/accounting audit. The registered Code Mode host was
observed for both CLI processes. **Both tasks failed:** four attempted MCP calls
were rejected before reaching the repository broker, no files changed, and none
of the four positive checks passed. This probe establishes no task-efficiency
benefit and authorizes no promotion. Formal qualification remains `UNASSESSED`.

## Frozen scope and identity

The development-only protocol was `upg-rc19-tools-transport-probe-v2`, frozen at
`6c6036062f068996179aa6d3ef87b547533db88a` before dispatch. It compared one Python
task family under control and treatment, using explicitly requested `gpt-6-luna`
with low reasoning. RC18 baseline source was
`29cf112b4629d6b90504b079e95a5370c206a4cb`. Candidate runtime/source identities
remained those registered for RC19 v1.

The engine digest was
`ca53b5aaf08d5011d6ac002b3492392d9bae336301d6796078458b8c96698504`;
the canonical private protocol digest was
`2f12f78694e7c30bd0f38a33ca8ed091a3bffb2ffb05f4b58cdae2239923bd2d`.
Independent review matched all 179 engine files to frozen Git blobs and checked
the [public protocol](../evolution/protocol/rc19-transport-probe-v2.json) against
the private protocol, task manifest and explicit configuration.

The [machine-readable audit](../audits/rc19-tools-transport-v2.audit.json) records
identity and evidence digests. Original v1/v2 records and snapshots are retained
unchanged; the [v1 failure audit](rc19-tools-development-v1.md) remains historical
evidence rather than being rewritten as a successful round.

## Actual cost of the failed probe

| Measurement | Control | Treatment | Total |
| --- | ---: | ---: | ---: |
| Fresh completed CLI turns | 1 | 1 | 2 |
| Input tokens | 37,496 | 37,364 | 74,860 |
| Output tokens | 224 | 265 | 489 |
| Completed-turn tokens | 37,720 | 37,629 | 75,349 |
| Reported cached input tokens | 33,024 | 32,000 | 65,024 |
| Reported reasoning output tokens | 0 | 0 | 0 |
| CLI subprocess seconds | 14.683391 | 12.911847 | 27.595238 |
| Full collector callback seconds | 16.176345 | 16.313511 | 32.489857 |
| Rejected MCP attempts | 2 | 2 | 4 |
| Executed broker tools | 0 | 0 | 0 |
| Passing tasks | 0 | 0 | 0 |
| Passing positive checks | 0/2 | 0/2 | 0/4 |

Cached input is a subset of input tokens and is not charged again in these
totals. Monetary billing and provider-internal retry billing remain unknown.
The final campaign budget elapsed was **34.01500000001397 seconds**. Its embedded
summary snapshot captured 33.828000000008615 seconds before the final checkpoint;
the later final value is selected here. Call/token counts, paired metrics and
acceptance gates agree. No original measurement is overwritten.

RC19 v1 plus this v2 probe used 10 known completed turns and 283,945 reported
tokens. This sum covers these two rounds only, not complete research cost.

## Host observation and actual failure

A separate bounded Windows process monitor observed two campaign CLI processes
and two direct-child Code Mode host processes. Both host image paths matched the
registered pathname, and the registered file bytes matched SHA-256
`f03190749208b5594fd5125d2d2b09e4ad00e2a1f74aeb11f60a6673dde83c43`.
The normalized host-path digest was
`a5d0a600ef858dd84d6b69e7850b0f35933c079990e9748ca075756fc4963738`.
The monitor recorded no path mismatch or unresolved query. It did not inspect
command lines, process environments, authentication material or process memory.
This is process-path observation and a registered-file hash check, not loaded
image verification or OS isolation attestation. The original capability receipt
continues to state that process-path attestation was not supplied by the adapter;
the later external observation is separate evidence.

Both raw CLI streams contain failed `upg_repo` calls to `repo_read` and
`repo_status`, with the exact error:

> MCP tool call requires approval, but approval policy is never

All four attempts have `status: failed` and no result. The independent broker
journals contain zero events, so these attempts are not counted as executed
repository tools. The raw evidence establishes this approval conflict for this
profile; it does not establish a supported configuration remedy. No new calls
or permission changes are inferred from the error.

Both CLI processes exited zero with one completed-turn usage record and a final
`validation: failed` declaration. Repository bytes remained exactly initial.
Independent AST/JSON contract inspection confirmed 0/4 positive checks. The
grader rejected missing real-tool evidence and the CLI/broker journal mismatch.
No registered task application code was executed.

## Integrity and decision

All 18 referenced raw-artifact hashes, both canonical result digests and receipt
digests, exact prompts, condition/call/engine bindings and final-file digests
matched. Thread and receipt identities were distinct. Both actual usage records
reconciled to the shared budget, with no replay, duplicate charge, unknown usage,
pending call, active dispatch lock or unknown-call fence.

The frozen collector's narrow host-disabled guard did not classify this new
approval error; its stored `transport_failure: null` and
`new_protocol_required: false` are preserved. They do not mean usable tools or
successful tasks were established. A corrected profile requires a new frozen
identity rather than replaying these calls.

The task-quality and net-benefit gates are `FAIL`. The single-family coverage
gate also fails, as expected for this capability probe. One pair cannot provide
a meaningful family-level uncertainty estimate. Token/CLI ratios from these
failed tasks cannot establish useful savings, and the full callback treatment
time was higher. Independent evaluation or promotion has not been admitted by
this result.
