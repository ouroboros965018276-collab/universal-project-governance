# Prepared RC18/RC19 native callback comparison (no calls authorized by this file)

The historical release is `29cf112b4629d6b90504b079e95a5370c206a4cb`.
The treatment revision is required as an explicit full 40-character commit SHA;
there is no default candidate revision. This harness is reusable source, not
evidence that the independent campaign has run or passed.
Its public `evolution.native_codex:runner(request)` and the current public
callback accept the same exact source/artifact/task/config contract. Their exact
release sources remain unchanged; CLI transport is instrumented identically in
both arms as described below. The public native API permits registering an
operator-selected grader. Both callbacks use one byte-identical inspectable
`upg_native_common_grader:grade` copied from the newly frozen treatment's strict
`task_benchmark.py`; its full source revision/hash/reference is registered.
This common grader is not represented as the historical release's default.
The parent independently rejects duplicate JSON keys, nonfinite JSON values,
bool/number type substitutions and any output-envelope or file-set deviation.
The exact historical and current native modules remain unchanged, while both
execute under the same separately pinned HTTP child-process instrumentation.
Thus the historical callback is measured under the common HTTP scaffold,
not claimed to reproduce historical default transport. No task replay or mocked
completion counts as a genuine observation.

The shared worker appends exactly five supported CLI `-c` values only for the
registered official binary's `exec` command: provider `upg_openai_http`, provider
name `OpenAI`, `wire_api=responses`, `requires_openai_auth=true`, and
`supports_websockets=false`. It sets no base URL, environment key, authentication
or header overrides. It preserves the CLI's own login and changes no host config.
Compiler/planner subprocess calls pass unchanged. Each dispatch has a durable
pending and returned/unknown instrumentation trace containing actual argv/hash,
source hash and raw output hashes. Trace writes and instrumentation run inside
the measured public callback and CLI wall. Returned process bytes remain intact
even if post-call trace persistence fails, so native known usage can be retained;
the parent rejects that incomplete trace after preserving known costs. No retry.

Use 32 genuine serial calls: two requested models (`gpt-6-luna`, `gpt-6.1-sol`,
low effort), eight newly frozen artifact tasks, two release arms. The task set
contains four known artifact families and two different fixtures per family.
None comes from the final tool-task set. Freeze all task JSON and positive
expected checks before dispatch; the native prompt exposes only task prompt,
payload and output schema, not `artifact_checks`. Structural JSON/AST/text
grading executes no generated application code. This is a separate scoped
independent artifact estimand, not a tool-usage or multi-provider qualification.

Each family has one exact plan context, distinct from the other families.
Run all four first-context fixtures before all four repeat-context fixtures.
The repeated fixture has a new ID, payload and expected artifact but exactly
the same context. `matched_order` in the prepared worker shuffles model/context
pairs using seed 19012 within each phase; paired arms stay adjacent and their
first position alternates, giving 2/2 order balance per model per phase.
Each arm consequently sees identical context order. Preparation caching is
not observation reuse: every task requires a new CLI turn and distinct receipt.

Create four persistent subprocess workers, one per release/model. Copy only
the exact release `evolution/__init__.py`, `contracts.py`, `native_codex.py` and
the identical common grader into separate ignored snapshot directories. Verify
every source hash; pin the worker file and raw manifest SHA in the new protocol.
The exact transport source and profile hashes are identical in all four workers.
The worker default is verification-only. Actual JSONL dispatch requires the
exact protocol SHA argument. It does not construct a client during initialization;
every measured call invokes the module-level public callback. Thus RC18 reads
config and constructs/hashes a fresh client on every callback, while RC19's
public LRU stays naturally populated inside its own persistent process.

Both arms use their release's exact source/compiler/license with no `runtime`
field. Both genuinely compile on the first occurrence of a context; RC19 reuses
verified preparation on repeats. Passing precompiled runtime only to control
would recreate the old preparation asymmetry and is prohibited. The first task
in each RC19 worker has both client and preparation cold; the next three are
client-warm/preparation-cold; repeats are client/preparation-warm. These are
process/cache states, not claims of cold OS caches or cold provider inference.

The parent collector needs independent review and a new public freeze before dispatch. Before each worker send,
atomically fsync a pending checkpoint. After receiving a complete result, retain
actual usage, full outcome, CLI thread receipt, raw artifact reference/hashes,
callback wall, worker/collector wall and local phase timings. Time the public
callback from immediately before entry through return: this includes config,
constructor, exact-source compilation/planning, executable verification, CLI,
grader and native raw/result/receipt persistence. Time the parent separately
from pending write through graded observation checkpoint commit, including IPC.
Measure worker startup and frozen snapshot preparation separately and include
them once in full campaign totals; never claim they were free. Historical phase
subdivision unavailable from receipts remains unknown; callback-minus-CLI is
the valid observed residual. Do not substitute RC19 `native_wall_seconds` or
the grader's CLI-time loss for full callback/collector wall.

Do not resume a partial campaign by restarting workers: that changes the frozen
cache schedule. Unknown calls, worker loss, timeout, invalid receipts and local
receipt replays stop with retained known costs and require reconciliation/new
protocol. An ordinary completed quality failure is retained and prevents a
quality/net-benefit PASS. All 32 responses must pass positive artifact, exact
scope and truthful `validation=not_run` checks and be fresh actual CLI calls.

Suggested stop thresholds are 32 calls, 1,500,000 reported total tokens, 7200
seconds, 180-second CLI timeout, zero automatic retries. These are post-call
usage stops, not guaranteed provider token caps or monetary billing. For scale,
the preserved RC18 16-call artifact comparison used 216,759 reported tokens;
per-call median was 13,575 tokens and 8.691 full callback seconds, maximum
13,943 tokens and 27.045 seconds. New costs/latency may differ.

Prespecify pooled full-callback and full-collector wall, actual tokens, per-model
ratios and cold/repeat descriptive strata. Bootstrap four whole family blocks,
preserving both requested models and cold/repeat together in each block, 4000
repetitions/seed19012. The separate native estimand A tests full-callback time
and quality: require all quality/freshness checks and full-callback time CI upper
<1. Report every token count and any token regression even if A's time gate
passes. Both native releases already canonicalize the plan JSON, so the larger
candidate Skill can increase native input tokens; plan-whitespace compaction
does not establish a native token saving. Define A's exact gates publicly before
its first call, preserve any A failure, and never change gates using results.

Tool estimand B retains its frozen joint token/time/per-model gates and the
requirements for a net-benefit merge; A cannot excuse a failed B joint gate.
Preserve both the earlier RC18 +23.7% callback result and the failed RC19 tool
net-benefit result. A positive native result establishes only a separate scoped
artifact/cache timing improvement, never joint token benefit or tool benefit.

The executable source is `evolution/experiments/native_paired/`. Run the no-model
CI checks with `python -B -m unittest discover -s tests -p test_native_paired.py`.
The preparation entry is `python -B evolution/experiments/native_paired/prepare.py`
with required `--repo`, `--output-directory`, `--artifact-root`, `--binary`,
`--git-binary`, `--model-catalog` absolute paths and `--treatment-revision` full
SHA. Output must be a fresh ignored `eval-workspaces/rc19-native-paired-*`
directory. Preparation extracts exact Git files, executes only each release's
trusted local planner, records source preparation cost, and dispatches zero
models. The existing official CLI model-list receipt must list both requested
IDs and low effort; listing is not a claim of verified access.

Use `python -B evolution/experiments/native_paired/parent.py --spec PATH` to verify
the prepared private protocol with zero models. Actual serial dispatch requires
both `--output FRESH-PATH` and `--allow-dispatch-protocol-sha256 EXACT-HASH`, after
public preregistration and independent freeze/review. All executable sources,
tests and this design are hashed into that protocol. Terminal records can be
read again without model replay; a partial/pending campaign cannot resume by
restarting workers. Keep raw task/response and broker contents private when
publishing aggregate audit summaries.

Preparation health: own unique ignored write/read/delete probe passed at
2026-10-12T14:11:45.2863757Z, entry `Codex subagent real_entry_survey ignored
native worker preparation`, in the confirmed rc17-offline-evolution worktree.
