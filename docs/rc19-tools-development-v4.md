# RC19 v4 matched real-tool development evaluation

Independent evidence audit passed for all 16 fresh CLI turns, including exact
usage, frozen identities, tool journals and final files. All 32 positive artifact
checks passed, and all 76 broker requests succeeded. **Strict task quality was
12/16 and the unchanged net-benefit gate failed.** Four turns contained raw CLI
network-error events. Those failures remain hard rejections even though the CLI
eventually completed and the final artifacts passed. Formal qualification
remains `UNASSESSED`; this result authorizes no promotion.

## Frozen scope

Protocol `upg-rc19-tools-development-v4` was committed at
`39447041e7782a32c9622b55a36b0d08ffdabff7` before dispatch. The engine digest was
`d07e5622ae7b086322519076ec017c194a6eed43ee2800b3c2229738aba57c7b`,
and the canonical private protocol digest was
`6768a01e689846682295161bf9283e601b81b6948417c6da71c851de564eb622`.
All 182 engine files matched frozen Git bytes before terminal. Post-terminal
audit reconstructed the same historical snapshot and verified every call's
engine/capability binding.

The [public protocol](../evolution/protocol/rc19-development-v4.json) compared
the exact registered RC18 and RC19 runtime Skill/planner strings under one
current bounded tool adapter. Baseline revision was
`29cf112b4629d6b90504b079e95a5370c206a4cb`. Explicitly requested `gpt-6-luna` and
`gpt-6.1-sol`, each with low reasoning, attempted the same four known development
families: registry, TOML, Python AST and documentation. Each model/family pair
received one control and one treatment turn. Seed 19012 fixed the order, with
two control-first and two treatment-first pairs per model.

Both conditions received the clarified common bounded-tool contract. Treatment
also received the new registered candidate Skill. These known development
tasks do not constitute independent holdout evidence. No independent-final
feedback was used. The budget remained 16 calls, 3,000,000 tokens and 3,600
seconds, with the existing strict quality and improvement thresholds.

## Actual cost and quality

| Measurement | Control | Treatment | Total |
| --- | ---: | ---: | ---: |
| Fresh completed CLI turns | 8 | 8 | 16 |
| Input tokens | 542,625 | 527,544 | 1,070,169 |
| Output tokens | 4,286 | 4,041 | 8,327 |
| Completed-turn tokens | 546,911 | 531,585 | 1,078,496 |
| Reported cached input tokens | 427,648 | 433,920 | 861,568 |
| Reported reasoning output tokens | 7 | 0 | 7 |
| Full collector callback seconds | 440.157125 | 412.882527 | 853.039652 |
| CLI subprocess seconds | 426.094452 | 401.544633 | 827.639086 |
| Successful broker requests | 40 | 36 | 76 |
| Rejected broker requests | 0 | 0 | 0 |
| Strict task-quality passes | 5/8 | 7/8 | 12/16 |
| Passing positive artifact checks | 16/16 | 16/16 | 32/32 |

Cached input and reasoning output are subsets of their corresponding token
totals. The completed-turn usage was known and reconciled; provider-internal
attempt counts, extra retry billing and monetary cost remain unknown. No
failure's reported tokens or time were removed or set to zero.

Final campaign budget elapsed was **855.3120000000054 seconds**. The embedded
and separate final summaries agree with that final value. Initial collector
setup took 1.3776048000145238 seconds, outside condition callback timings but
inside campaign elapsed. Original measurements are unchanged.

The [v1 failed round](rc19-tools-development-v1.md),
[v2 failed probe](rc19-tools-transport-v2.md),
[v3 transport probe](rc19-tools-transport-v3.md),
[v3 matched development round](rc19-tools-development-v3.md), and this round
together used **44 known completed CLI turns and 2,855,061 reported tokens**.
Fourteen turns failed their frozen task-quality gates: ten in v1/v2 and four in
this round. These five rounds are not complete research cost.

## Preserved network failures

| Requested model / family / condition | Raw reconnection errors | HTTPS fallback diagnostic | Strict quality |
| --- | ---: | ---: | --- |
| gpt-6-luna / documentation / control | 1 | 0 | FAIL |
| gpt-6.1-sol / registry / control | 2 | 0 | FAIL |
| gpt-6.1-sol / Python / treatment | 1 | 0 | FAIL |
| gpt-6.1-sol / Python / control | 4 | 1 | FAIL |

The eight raw `type: error` messages reported TLS handshake EOF during stream
reconnection. The fourth listed turn also emitted an `item.completed/error`
diagnostic announcing fallback from WebSockets to HTTPS. The frozen grader
recorded `cli-turn-error` for the reconnections and
`unregistered-cli-item:error` for that diagnostic; the latter turn also retained
`scope_ok: false`. All four hard failures and their exact recorded failure lists
were reproduced in independent review. No error event was retrospectively
ignored or reclassified to pass the gate.

All 16 CLI processes exited zero and produced one completed-turn usage record
and a final validation-passed declaration. Static output success does not
remove the stricter transport-quality failures. The CLI handled its own
reconnection/fallback behavior; the harness did not replay these measured turns.
The displayed reconnection counters do not establish the number or billed cost
of provider-internal requests. Their uncertainty remains explicit.

## Measured comparison and decision

| Metric | Treatment/control ratio | Registered 95% interval |
| --- | ---: | ---: |
| Total tokens | 0.971977 | [0.928761, 0.997599] |
| Full collector callback time | 0.938034 | [0.818683, 1.025041] |
| CLI subprocess time | 0.942384 | [0.828391, 1.028108] |
| Broker request count | 0.900000 | [0.795455, 1.026316] |

The token point estimate fell 2.8023%, and its registered interval upper bound
was below 1. Full callback time fell 6.1966% in the point estimate, but its
interval upper bound exceeded 1. Luna callback time increased 0.7736%; Sol
callback time decreased 9.2190%. Thus strict task quality, overall time
uncertainty and per-model time improvement all failed the unchanged joint
gate. Token improvement alone does not establish net benefit.

Independent code reproduced all overall and per-model bootstrap metrics and
intervals exactly: 4,000 paired task-family block resamples stratified by
requested model, seed 19012. These estimates retain all failed turns and all
their costs. No outlier, network-error turn or slow call was excluded. The
observed network failures and fallback do not identify how much timing
difference was caused by transport, provider service, scheduling or guidance.

The zero denied reads are an observed difference from v3 development. Both
conditions received a changed common contract, and service conditions differed;
the cross-round difference cannot isolate a candidate-only causal effect.
No unsupported or ambient tool executed. All 76 broker responses were successful:
25 reads, 16 patches, 16 static validations and 19 status inspections.

## Integrity and measurement limits

All 144 referenced raw-artifact hashes, 16 canonical result digests and 16
receipt digests matched. Distinct thread/receipt identities, exact full frozen
prompts, call keys, source/condition/model/capability bindings and preregistered
order matched. Raw CLI arguments and responses matched independent broker
journals. Final repository snapshots, exact file sets, protected bytes and all
32 JSON/TOML/AST/text contracts passed. Successful validation/status evidence
referred to the final state. No replay, duplicate charge, pending call,
unknown completed-turn usage or active dispatch fence was found.

The [machine-readable audit](../audits/rc19-tools-development-v4.audit.json)
preserves evidence digests, exact metrics and the four hard failures. Earlier
rounds remain unchanged. This round has no separate process-path monitor
attestation. Requested model identities do not verify provider-internal model
identity or establish multiple provider families. OS isolation is unverified,
and submitted application code was parsed rather than executed.

Both conditions used preprepared runtime Skill and planner text. Full collector
timing covers per-dispatch preparation/verification, CLI, grading and evidence
commit. Runtime compilation/planner generation and initial client setup remain
outside condition timing. **Native preparation-cache/client-reuse gains and
historical-versus-current callback end-to-end gains were not measured.** A
separate native experiment cannot excuse this tool campaign's failed joint gate.

Net benefit remains `FAIL`, formal qualification remains `UNASSESSED`, and no
candidate was promoted or independent evaluation admitted by this result. Any
corrected transport profile or later development requires a new frozen identity
while preserving these records, costs and acceptance criteria.
