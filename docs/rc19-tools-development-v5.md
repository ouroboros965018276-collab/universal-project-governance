# RC19 v5 partial real-tool development audit

**Evidence verification passed; the experiment is blocked and net-benefit admission remains FAIL.** Six genuine completed CLI turns reported 407,496 tokens. The seventh dispatch failed with a model-capacity message and no completed-turn usage. Its cost is unknown, and the pending fence prevents automatic replay. The owner requested a stage pause; final independent B and native A both remain at zero calls.

## Frozen scope and verification

The [registered protocol](../evolution/protocol/rc19-development-v5.json) was frozen at `929906bd29ceb581d55fcaf9ebb28fd2a22eba0d`, engine `479a117121c92cd348555826c1b7652529819fea67dd5959cd85f6e68af963dc`, private protocol `088690c9543e3f4811435542b60c6206da356f63c6eb07c7c06edb106ec6baa0`. Independent review reconstructed all 192 historical engine files from Git, reconciled all seven dispatch directories, and verified raw hashes, exact prompts/commands, source/runtime/capability/task bindings, order, usage and receipt identities. Later unfinished harness edits do not change or rebind this measurement.

The planned comparison was 16 calls across four known development families and two requested OpenAI models, `gpt-6-luna` and `gpt-6.1-sol`, at low effort. Both arms used the same registered child HTTP transport and bounded repository broker. Only documentation and registry tasks completed before the interruption. These are development observations, not independent qualification. The budget was 16 calls, 3,000,000 tokens and 3,600 seconds; uncertainty, rather than a budget limit, stopped this round.

## Recorded cost and quality

| Completed-turn measurement | Control | Treatment | Total |
| --- | ---: | ---: | ---: |
| Completed CLI turns | 3 | 3 | 6 |
| Input tokens | 200,586 | 203,934 | 404,520 |
| Output tokens | 1,585 | 1,391 | 2,976 |
| Reported total tokens | 202,171 | 205,325 | 407,496 |
| Reported cached input tokens | 150,400 | 131,584 | 281,984 |
| Reported reasoning output tokens | 0 | 0 | 0 |
| Full collector callback seconds | 109.899969 | 100.339609 | 210.239579 |
| CLI subprocess seconds | 108.129488 | 98.475551 | 206.605039 |
| Successful broker requests | 16 | 13 | 29 |
| Strict task-quality passes | 2/3 | 3/3 | 5/6 |
| Positive static artifact checks | 6/6 | 6/6 | 12/12 |

All 29 broker requests were reconciled against actual CLI tool arguments and replayed as bounded data transformations; final files and current validation/status evidence matched. Each completed turn made an actual permitted repository edit. Six completed turns had six distinct CLI thread identities; the unknown dispatch added a seventh distinct thread. Thread IDs are local CLI identities, not provider request IDs. Cached-input and reasoning-output counts are subsets of input/output totals.

The first Luna/control documentation turn recovered from a raw body-decode transport error and eventually completed its edits and both static checks. The frozen grader nevertheless recorded `cli-turn-error`, so strict quality remains FAIL. This audit reproduces that failure without weakening the rule or regrading it to pass. The result is therefore **5/6 strict passes among completed turns, or five passes among seven dispatches**, with the last dispatch unscored.

The seventh dispatch was `gpt-6.1-sol`, treatment, Python. Raw events contain both an error and `turn.failed` with “Selected model is at capacity. Please try a different model.” CLI exit was 1 and there was no `turn.completed` usage. Its call directory `gpt-6.1-sol/calls/0f4e04868231f8b320f46aba8d38b27c5f69e1f236750c7a5ff9e930361922ab` retains `receipt.json`, `pending.json`, command/prompt and raw outputs, but no `result.json` or broker journal. The separate model-root `UNKNOWN_CALL.json` and collector pending record also remain. This is neither a zero-token call nor a reusable completed observation. No harness replay occurred.

## Incomplete diagnostics and decision

Only three of eight planned matched pairs completed. Their treatment/control token ratio is **1.015601**, while full callback time is **0.913009** and CLI time is **0.910719**. These incomplete estimates are diagnostics only. Luna tokens and callback time both regressed; coverage is insufficient, and the newly registered joint-family token/time intervals are both null. The unchanged original gates plus the additional joint-family gates produce **net-benefit FAIL**. No speedup, net benefit, promotion or Stable conclusion follows.

Across the preserved RC19 rounds there are now **50 known completed turns and 3,262,557 reported tokens, plus one additional dispatch with unknown usage: 51 recorded dispatches**. This is not complete research cost; provider-internal attempts, retry billing and monetary charges remain unknown. Known elapsed time for the failed completed turn and the unknown dispatch is retained.

The [machine-readable audit](../audits/rc19-tools-development-v5.audit.json) contains per-call hashes, reported costs, exact failure denominators and the unchanged partial summary. Original checkpoints, raw evidence, prior rounds and the already frozen A protocol remain intact. Formal qualification remains `UNASSESSED`; the accepted installed Skill remains RC18.
