# RC19 v3 matched real-tool development evaluation

Independent audit passed for all 16 fresh CLI turns: all 16 tasks and 32 positive
checks passed, and raw usage, tool journals, final files and frozen identities
matched. **The unchanged net-benefit gate failed.** Treatment used 3.6469% fewer
reported tokens but took 9.3737% longer in full collector callback time. Both
token and time uncertainty intervals included regression, and both requested
models had higher treatment callback time. This development result establishes
no verified net benefit and authorizes no promotion. Formal qualification
remains `UNASSESSED`.

## Frozen scope

Protocol `upg-rc19-tools-development-v3` was committed at
`47f665d1644f4c18adb25cde75413701bb430dbc` before dispatch. It compared the exact
registered RC18 and RC19 runtime Skill/planner strings using the same current
bounded tool adapter. Baseline revision was
`29cf112b4629d6b90504b079e95a5370c206a4cb`. Explicitly requested `gpt-6-luna` and
`gpt-6.1-sol`, each with low reasoning, attempted four known development task
families: registry, TOML, Python AST and documentation. Each model/family pair
had one control and one treatment turn. Seed 19012 fixed pair order and balanced
condition order to two control-first and two treatment-first pairs per model.

The frozen engine digest was
`392a0fc0c62b67c12ea7d688823fc1414b0fd4428c26e3ab9265469e40ad7899`;
the canonical private protocol digest was
`15e04e138e52421795f15412135fc84b43200035b2760a94e65fd4ff816ded47`.
All 181 engine files matched frozen Git bytes before collection completed.
Post-terminal audit reconstructed that historical Git snapshot and verified its
digest against every call binding. Later development source changes do not
alter this measurement identity.

The [public protocol](../evolution/protocol/rc19-development-v3.json) retained
the existing strict acceptance thresholds and a budget of 16 calls, 3,000,000
tokens and 3,600 seconds. These were known development tasks, not independent
holdout evidence. No independent-final feedback was used.

## Actual cost and measured comparison

| Measurement | Control | Treatment | Total |
| --- | ---: | ---: | ---: |
| Fresh completed CLI turns | 8 | 8 | 16 |
| Input tokens | 679,964 | 655,136 | 1,335,100 |
| Output tokens | 4,951 | 4,801 | 9,752 |
| Completed-turn tokens | 684,915 | 659,937 | 1,344,852 |
| Reported cached input tokens | 542,720 | 524,928 | 1,067,648 |
| Reported reasoning output tokens | 52 | 48 | 100 |
| Full collector callback seconds | 232.648758 | 254.456485 | 487.105244 |
| CLI subprocess seconds | 224.911689 | 242.188972 | 467.100661 |
| Broker requests, including rejected reads | 52 | 50 | 102 |
| Successful broker operations | 47 | 48 | 95 |
| Rejected broker reads | 5 | 2 | 7 |
| Passing tasks | 8 | 8 | 16 |
| Passing positive checks | 16/16 | 16/16 | 32/32 |

Cached input and reasoning output are subsets of their corresponding token
totals. Monetary billing and provider-internal retry billing remain unknown.
All attempts, including rejected reads and subsequent recovery, remain in the
actual reported usage and timing.

| Metric | Treatment/control ratio | Registered 95% interval |
| --- | ---: | ---: |
| Total tokens | 0.963531 | [0.801357, 1.146222] |
| Full collector callback time | 1.093737 | [0.943478, 1.218657] |
| CLI subprocess time | 1.076818 | [0.913392, 1.212140] |
| Broker request count | 0.961538 | [0.836364, 1.104167] |

The registered method was a paired task-family block bootstrap stratified by
requested model, with 4,000 resamples and seed 19012. An independent
implementation reproduced every stored overall and per-model metric and
interval exactly. Four known families per model provide limited development
evidence; this is not a formal provider-family qualification.

| Requested model | Token change | Full callback time change | Broker requests control/treatment |
| --- | ---: | ---: | ---: |
| gpt-6-luna | -5.2719% | +2.6831% | 24 / 22 |
| gpt-6.1-sol | -1.9697% | +13.3567% | 28 / 28 |

Both models' token point estimates improved, but the token interval upper bound
failed the strict improvement gate. Both full callback point estimates
regressed, and the overall time interval upper bound also failed. All freshness,
matched-collection, quality, receipt-uniqueness and family-coverage gates passed.

Final campaign budget elapsed was **489.6570000000065 seconds**. The embedded
summary captured 489.3440000000119 seconds before the last checkpoint; the
separate final summary agrees with the final budget. Counts, metrics and gates
agree. Initial collector setup took 1.829985000018496 seconds, outside condition
callback timings but inside campaign elapsed. Original records are unchanged.

Together with the [v1 failed round](rc19-tools-development-v1.md),
[v2 failed probe](rc19-tools-transport-v2.md) and
[v3 transport probe](rc19-tools-transport-v3.md), these four RC19 rounds used
**28 known completed turns and 1,776,565 reported tokens**, including the ten
failed-task turns in v1/v2. This is the cost of these four rounds only, not full
research cost.

## Raw quality and bounded denials

All 144 referenced raw-artifact hashes, 16 canonical result digests and 16
receipt digests matched. Thread and receipt identities were distinct. Exact
Skill/plan/task delivery, call keys, condition/model/capability/engine bindings,
preregistered order and actual budget records reconciled. Every registered CLI
tool response matched its independently stored broker arguments and result.
No unknown or ambient tool event, duplicate charge, replay, pending call,
unknown usage or active dispatch fence was found.

Independent JSON/TOML/AST/text checks passed all 32 positive contracts. Protected
file bytes and the exact registered final-file sets also matched. Every task
had successful read, patch, static-validation and status evidence, with the
latest successful validation/status referring to the final repository state.
The submitted application code was parsed rather than executed. Sixteen
PowerShell shell-snapshot warnings remain in the original stderr records.

Seven registered read requests guessed unsupported project-helper paths or
other files outside the bounded scope. The broker rejected all seven before
reading those paths. Their failed MCP statuses and exact rejection results
matched the broker journals; subsequent scoped reads and final checks passed.
The frozen grader permits such recovered registered-tool denials. This audit
preserves that rule and the failures instead of changing the historical quality
gate or calling every request successful. The 102 requests comprise 95
successful operations and seven denied reads.

The adapter bound the registered CLI, Code Mode host file, package manifest and
tool schema. This development round has no separate process-path monitor
attestation; the [earlier probe's host observation](rc19-tools-transport-v3.md)
does not attest every later process. Provider-internal model identity and OS
isolation remain unverified.

## Diagnostic limits and decision

The 21.807727-second treatment callback increase comprises 17.277283 additional
CLI seconds and 4.530443 additional seconds outside the CLI. These are measured
phase differences, not proof of a server, scheduler or cache cause. Luna CLI
time fell 1.5594% while its complete callback time rose; Sol CLI time rose
13.1502%. Provider cached-token totals differed by arm. No causal explanation
can be assigned from these observations alone.

Treatment made two fewer total requests because it had three fewer denied
reads, while successful operations increased from 47 to 48. The measured
request reduction does not establish reduced successful work or latency.
This is actionable development evidence for making the actual tool contract
and unavailable helper surfaces explicit before another frozen evaluation.

Both conditions used one current tool adapter and preprepared runtime Skill and
planner text. Full collector timing includes per-dispatch preparation and
verification, CLI, grading and evidence commit. Runtime compilation/planner
generation and initial client setup are outside condition callback timing.
**Native preparation-cache/client-reuse gains and historical-versus-current
callback end-to-end gains were not measured.** This result cannot reverse the
earlier RC18 latency finding, and it supplies no cross-provider evidence.

The [machine-readable audit](../audits/rc19-tools-development-v3.audit.json)
preserves exact metrics, denials, identities and evidence digests. Net benefit
remains `FAIL`; formal qualification remains `UNASSESSED`. No learned candidate
was promoted and no independent evaluation is admitted by this failed result.
Any later development uses a new frozen identity and retains these costs and
the existing acceptance criteria.
