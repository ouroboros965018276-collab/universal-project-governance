# Offline governance evolution

Current candidate: **3.0.0-rc.19 — Project Fact Recovery and Measured Execution Cost**.

RC17 introduced the repository-only optimizer around the compiled UPG runtime. The
installed Skill still needs no model backend and its optional helpers support
Python 3.8+. Evolution needs Python 3.10+ with current security patches (historical
baseline extraction requires 3.10.12+) and uses the standard library; it never
installs a model SDK or reads account credentials implicitly.

RC18 repairs demonstrated task-grader false positives, compacts canonical
instructions, and adds explicitly registered native-CLI artifact measurements.
Eight paired RC17/candidate artifact-task measurements are complete. The v1
development matrix stopped on a controller error; the fresh preregistered v2
round completed all nine arms and passed experiment-record audit. Skill bytes, actual prompt tokens, completed-turn
tokens, CLI wall time and full evaluator callback time are separate observations.

## Candidate and trust boundaries

`governance-src/` remains the only normative source. A candidate comprises a model
`d` and three normalized presentation parameters `theta`. Search configuration
`phi` stays offline. The compiler maps theta to a complete policy presentation
permutation; policy selection, dependency closure, safety, evidence, reporting,
scope and handoff requirements remain mandatory.

UPG native reflection proposes bounded edits to a temporary view. Each edit binds a unique
policy/field and its original hash. Missing or ambiguous targets, stale hashes,
protected fields and empty required text reject the complete patch. Text edits
are not evidence of semantic equivalence; promotion needs independent task tests.

RC19 uses its own reflection, duplicate-consensus, conditional merge/selection,
training-memory and atomic patch implementation. A single unambiguous edit needs
no merge or ranking call. All model requests use one explicit, budgeted backend;
unknown usage stops further dispatch. No upstream package is imported or needed.
Licensing and historical/design references remain in `third_party/notices/`;
historical protocols and audit records keep their original identities.

## Joint search

- Native reflection learns limited textual patches from scored development rollouts.
- Seeded chaotic simulated annealing explores legal candidates, with cooling,
  reheating and finite-precision cycle detection. Exploration acceptance never
  authorizes a release.
- JADE-style differential evolution maintains separate structural populations,
  learns successful mutation/crossover controls and keeps a bounded archive.
- A local quadratic surrogate uses measured samples, full-rank coverage,
  residual checks and leave-one-out direction stability. Only credible negative
  curvature produces two trust-region candidates, each requiring real evaluation.

Executable candidates are deduplicated after parameter legalization, including
presentation plateaus. The same cached evaluation never becomes another sample.
Call, token, elapsed-time and candidate budgets bound the controller, including
selection and replayed learning accounting. Failed calls and retries consume the
same shared budget; unknown reported totals block further calls. Receipts must
distinguish requested limits from provider-enforced limits and one adapter
invocation from provider-internal attempts. Metering after a response is a stop
threshold, not a guarantee against a request overshooting the remaining tokens.

## Commands

From the repository root:

```bash
python -m evolution run --spec evolution/protocol/upg-evolution-v2.json --output eval-workspaces/evolution/run.json
python -m evolution inspect --run eval-workspaces/evolution/run.json
python -m evolution ablate --spec evolution/protocol/upg-evolution.json --output eval-workspaces/evolution/matrix
python -m evolution run --spec evolution/protocol/upg-evolution.json --output eval-workspaces/evolution/run.json --resume
python -m evolution verify --run eval-workspaces/evolution/run.json
python -m evolution propose --run eval-workspaces/evolution/run.json --output eval-workspaces/evolution/proposal
```

The default run uses a clearly marked local fixture backend. It exercises the
actual upstream learning path and numerical search against deterministic
compiler/planner checks. Its objective is UTF-8 context bytes, **not tokens,
task quality, elapsed-time savings or model efficacy**. A flat surrogate correctly
declines a negative-curvature escape. `verify` returns a nonzero status while
empirical evidence is missing; `propose` then refuses to create a promotion.

For real development tasks, explicitly provide trusted, installed Python
callbacks via `--runner module:function --backend module:function` and register
training and separate selection tasks in the spec. Selection is scored after
search, never fed into reflection or optimizer memory. Final tasks stay outside
both development stages. Split task identities must be disjoint; final admission
additionally requires disjoint projects and task families.
The runner receives candidate/task/model/config/attempt/cache identity and must
return status, task-grader outcome, actual usage and provider receipt. The
learner backend receives system/user/stage/completion limit and returns
`(text, usage)`. Missing usage fields remain unknown. Credentials remain the
chosen backend's responsibility and follow its official authorization path.

### Native CLI development adapter

`evolution.native_codex:runner` and `evolution.native_codex:backend` reuse an
explicitly selected, already authenticated official CLI. `UPG_NATIVE_CONFIG`
must name an absolute local JSON configuration with the registered binary,
requested model, reasoning effort, artifact directory and timeout. It accepts no
login material. Freeze the adapter's configuration/binary/grader binding in
`runner_config` before calls; the runner also binds the exact canonical source,
compiler, compiled runtime and task artifact. A changed execution input invalidates
cached evidence.

The original v1 spec remains `evolution/protocol/rc18-native-development.json`.
The fresh v2 spec is
`evolution/protocol/rc18-native-development-v2.json`:

```bash
python -m evolution ablate --spec evolution/protocol/rc18-native-development-v2.json --output eval-workspaces/evolution/rc18-native-v2-matrix --runner evolution.native_codex:runner --backend evolution.native_codex:backend
```

This workload asks for complete file contents in JSON, with validation explicitly
`not_run`; task instructions prohibit tools and the grader never executes generated code. A trusted
artifact grader checks the requested result and preserved files. The adapter
retains actual reported completed-turn usage and CLI wall time in local receipts.
The requested `gpt-6-luna` name is not yet provider-confirmed, provider-internal
retries are not independently accounted, and the native output token limit is
an instruction rather than an enforced CLI ceiling. These limits must accompany
any result. A successful file response establishes neither real tool execution
nor a cross-Agent handoff or independent multi-family efficacy.

Checkpoints use atomic same-volume replacement and bind source, engine, vendor,
protocol and callback identities. A callback interrupted in flight leaves a
pending receipt; resume rejects it until independently reconciled. Exclusive
writer locks prevent concurrent use of one checkpoint; a lock left by a killed
process needs explicit recovery. Model and
task outputs stay in the ignored experiment workspace, outside user projects.

### Observed RC18 artifact measurements

The [paired summary](../qualification/pilots/rc18-native/paired.summary.json)
records eight prespecified task pairs at source
`e08faff3c37bb2736e387a5ca743b3b20644f9dd`, using 16 fresh calls and 216759
completed-turn tokens. Every positive task check passes. The ratios below compare
RC18 to RC17; intervals use the preregistered paired-family bootstrap.

| Observation | RC17 | RC18 | Change | Ratio 95% interval |
|---|---:|---:|---:|---:|
| Input tokens | 109950 | 105715 | −3.85175% | [0.96072, 0.96225] |
| Total tokens | 110504 | 106255 | −3.84511% | [0.96082, 0.96226] |
| Full evaluator callback seconds | 70.98168 | 87.80255 | +23.6975% point estimate | [0.95923, 1.51345] |

Full callback time includes isolated compilation, planning and grading. Its
interval includes 1, so no timing improvement is established. Compiled
`SKILL.md` separately shrinks from 11144 to 7940 UTF-8 bytes (28.75%); this byte
reduction is not a token measurement. This eight-pair artifact result in one
requested model does not establish tool execution, independent model families,
operator contribution or generalization.

The [v1 round summary](../qualification/pilots/rc18-native/round-v1.summary.json)
retains 39 completed-turn calls and 553938 tokens, including the paired 16 calls
above. The development matrix stopped in the full arm with `SourceBridgeError`:
an invalid learner edit was safely rejected, but the controller incorrectly
aborted the arm; five arms did not run. All original checkpoints and costs are
preserved. After charged invalid-proposal handling was repaired, the fresh v2
round completed 9/9 arms and passed independent audit of the experiment records.
Its 188 actual CLI turns comprise 158 task calls and 30 learner calls, consuming
2684192 tokens. All 158 raw task results pass mechanical regrading; final-task
dispatch is 0. This verifies bounded development execution without establishing
causal algorithm benefit. Runtime Skill and task grader remain unchanged from
the paired tested revision. Final-task feedback is not reused, and no learned
candidate is promoted.

Two Windows checkpoint `Path.replace` operations were temporarily denied.
Already charged calls were reconciled before each recovery under the same frozen
protocol and engine, with additional calls included in budgets and totals. The
occupying process and specific cause remain unconfirmed. Repository-only bounded
checkpoint-I/O retry hardening was added after measurement; final local regression
passes 299/299 tests in 98.700 seconds and all eight local release gates pass.
Hosted CI passes 11/11 at measured freeze
`8d1cb51945c5d98bf3db7c2e72557d7e50274275`; final PR/main CI is recorded separately.
The runtime, algorithm and protocol are
unchanged, and measured receipts retain their original engine identity rather
than being rebound to the repaired release engine. The [release audit](../audits/rc18-real-evaluation.audit.json)
records both identities; the [real-evaluation report](../qualification/pilots/rc18-native/README.md)
retains the complete campaign limits.

Persistent checkpoint replacement failure propagates through the controller
without another `save_run`, so exception handling does not overwrite the retained
temporary file or expand the six-attempt bound. The focused I/O suite passes 46
tests, including seven added methods covering 12 fault scenarios; independent
read-only code review passes.

| Cost scope | Actual CLI turns | Reported tokens |
|---|---:|---:|
| v1, including paired 16 turns / 216759 tokens | 39 | 553938 |
| v2 nine-arm round | 188 | 2684192 |
| Trials subtotal | 227 | 3238130 |
| Separate capability probe | 1 | 14921 |
| Total including probe | 228 | 3253051 |

## Independent admission

`ablate` executes all nine registered arms, including actual historical Git
archives selected by the frozen spec, with resumable per-arm ledgers. Removing modules reallocates search
rounds to remaining modules under the same overall caps. Unused budget stays
visible; identical caps do not prove identical actual consumption. The matrix is
a development comparison, not independent final evidence.

`evolution/protocol/upg-evolution.json` retains RC17's RC15 primary historical
baseline and RC16 pre-upgrade regression baseline. The RC18 native development
spec uses the exact RC17 release as its current-version comparison. The protocol
specifies isolated training/selection/final families, equal-budget controls and
ablations, actual provider usage, paired uncertainty and noncompensatory gates.
Operator-removal controls use `--disable reflection|annealing|de|curvature`;
`--ordinary` supplies the ordinary-perturbation comparison. Runtime and optimizer
costs must be reported separately and by model family, including failed tasks.

Independent evidence requires a precommitted holdout freeze, immutable raw
provider/context/grader receipts, candidate/protocol bindings, independent actor,
unexposed task families and all registered arms at equal budgets. Report
implementation, empirical efficacy and formal qualification separately. The
existing `qualification/` remains authoritative for release qualification.

Targets (not observed results) include at least 25% governance-context token
reduction; paired total-token ratio <=0.85 and time ratio <=0.90, each with a 95%
upper bound below 1, with safety/quality/handoff nonregression. Break-even is
calculated separately for tokens, money and time only when positive, reliable
per-task savings have been established. No global optimum is claimed for this
mixed discrete/continuous search.

Completed paired artifact measurements, audited v2 execution and pending release work are recorded
in `PROJECT_STATE.md`; the RC17 audit retains its original engineering-only scope.
The eight-pair artifact comparison cannot satisfy the independent final-evidence
or formal qualification contract. Empirical admission remains BLOCKED and formal
qualification UNASSESSED. No qualifying locked trial has run; Stable remains NOT
ACHIEVED. Pre-merge installation snapshot: the user-level Skill is RC17; RC18 is
prepared but not installed at that snapshot. Later deployment requires its own
observed acceptance record.
