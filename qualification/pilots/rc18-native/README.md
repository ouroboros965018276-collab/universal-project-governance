# RC18 native-model evidence

RC18 fixes positive task grading and reduces the canonical installed Skill from 11,144 to 7,940 UTF-8 bytes (28.75%). Eight prespecified RC17/RC18 task pairs completed before the development search. Their actual completed-turn tokens decreased from 110,504 to 106,255 (3.8451%), with all 16 artifacts passing mechanical grading. This is a bounded improvement for these file-artifact tasks on one requested model, not a general Agent qualification.

The frozen paired source is `e08faff3c37bb2736e387a5ca743b3b20644f9dd`. The candidate template was fixed before the trials; it is not a winner selected by the subsequent nine-arm search. Family-stratified paired bootstrap used the registered seed 1729 and 4,000 repetitions. The total-token treatment/control ratio is 0.96155, with a descriptive 95% interval [0.96082, 0.96226]. The full evaluator callback time increased from 70.982 to 87.803 seconds (point estimate +23.70%, ratio interval [0.95923, 1.51345]). There is **no demonstrated speedup**. Native CLI process timing is reported separately in [paired.summary.json](paired.summary.json).

## Nine development arms

The completed v2 matrix used frozen source `8d1cb51945c5d98bf3db7c2e72557d7e50274275`, requested `gpt-6-luna` with low reasoning, seed 1729, one training task and one selection task. Each arm had the same upper limits: 60 model calls, 1,200,000 tokens, 7,200 active seconds and 32 candidates. Actual spending differed. Removed operators redistributed the registered search allocation; this single-seed small development matrix does not estimate causal operator contributions.

| Arm | Completed CLI turns | Completed-turn tokens | Executable candidates |
| --- | ---: | ---: | ---: |
| RC15 | 2 | 27,146 | 0 |
| Latest baseline (RC17) | 2 | 27,462 | 0 |
| SkillOpt only | 14 | 206,807 | 1 |
| Full | 25 | 378,799 | 21 |
| Without SkillOpt | 32 | 434,999 | 29 |
| Without chaos | 27 | 388,822 | 22 |
| Without differential evolution | 29 | 423,650 | 19 |
| Without curvature | 20 | 286,239 | 13 |
| Ordinary annealing | 37 | 510,268 | 30 |
| **Total** | **188** | **2,684,192** | |

These are 158 real task turns and 30 learner turns. The independent reviewer regraded all 158 raw task results successfully, reconciled actual usage with the budget, and verified 188 distinct native CLI thread/harness identities and raw receipt hashes. Final-task dispatch during this matrix was zero. Cache observations and repeated paid work after checkpoint recovery must not be counted as additional independent evidence; details appear in [matrix.summary.json](matrix.summary.json) and [matrix.independent-audit.json](matrix.independent-audit.json).

SkillOpt and curvature had zero accepted proposals in this campaign; some differential-evolution and annealing exploration proposals were accepted. Exploration acceptance is not promotion. No learned candidate was promoted. Six paid learner proposals failed source-field validation and were rejected while their actual costs remained charged.

## Failures, recovery and total observed cost

The v1 matrix stopped when a paid learner returned an invalid source-field target. The original costs and failure remain in [round-v1.summary.json](round-v1.summary.json). The controller repair keeps the bridge strict and records known paid invalid proposals as rejections; unknown usage, terminal provider failures and budget overruns still stop execution. V2 was registered and frozen before its first call.

Two v2 Windows checkpoint replacements were temporarily denied. The occupying process and exact cause are unverified. Each stopped writer was independently reconciled against all completed native receipts before supported resume under the same frozen engine and protocol. Restarted unfinished stages can incur additional paid work; all such charges remain inside the same arm budget. The final campaign completed without pending or unknown calls. [matrix.interruption.json](matrix.interruption.json) retains both interruption and reconciliation records. A later release-only repair retries replacement of the same already-fsynced temporary bytes at most six times, with 0.54 seconds total backoff; persistent failure retains the old target and complete temporary file. It does not resend requests or change the measured engine retrospectively.

V1, including the paired trials, used 39 calls and 553,938 tokens. V2 used 188 calls and 2,684,192 tokens. Combined trials therefore used **227 calls and 3,238,130 tokens**. The separate capability probe used one call and 14,921 tokens; the observed native total including that probe is **228 calls and 3,253,051 tokens**. The paired 16 calls are already included in v1 and are not added again. These are reported completed-turn tokens, not verified monetary billing or the full research cost.

## Evidence boundaries

The existing authenticated official Codex CLI was used after explicit owner authorization to send the generated Skill, compiled plan and fixed synthetic task files to OpenAI. Model-generated artifacts were parsed and mechanically graded, never executed as model code. This campaign does not establish provider request independence, actual server model identity or complete provider-internal retry billing. Raw owner-local receipts are retained outside the public report; public audits include their record hashes without host paths, thread identifiers or model content.

The formal gate remains unchanged: empirical `BLOCKED`, formal qualification `UNASSESSED`, `promotion_allowed: false`. The required multi-family coverage and formal thresholds were not met. Monetary/time break-even and causal algorithm savings remain unassessed. RC18 is a release candidate with a measured bounded token improvement, not Stable or a claimed global optimum.

The [grader regression report](../../../docs/rc18-grader-regressions.md) records the false-success reproductions and acceptance checks. The [release audit](../../../audits/rc18-real-evaluation.audit.json) distinguishes paired, development and post-measurement release identities.
