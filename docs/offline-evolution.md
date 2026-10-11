# Offline governance evolution

Current candidate: **3.0.0-rc.18 — Grader Validity and Measured Runtime Compression**.

RC17 introduced the repository-only optimizer around the compiled UPG runtime. The
installed Skill still needs no model backend and its optional helpers support
Python 3.8+. Evolution needs Python 3.10+ with current security patches (historical
baseline extraction requires 3.10.12+) and uses the standard library; it never
installs a model SDK or reads account credentials implicitly.

RC18 repairs demonstrated task-grader false positives, compacts canonical
instructions, and adds explicitly registered native-CLI artifact measurements.
Candidate validation, the nine-arm development run and eight paired RC17/candidate
task results are pending. Template bytes, actual prompt tokens, completed-turn
tokens, CLI wall time and task quality are separate observations.

## Candidate and trust boundaries

`governance-src/` remains the only normative source. A candidate comprises a model
`d` and three normalized presentation parameters `theta`. Search configuration
`phi` stays offline. The compiler maps theta to a complete policy presentation
permutation; policy selection, dependency closure, safety, evidence, reporting,
scope and handoff requirements remain mandatory.

SkillOpt proposes bounded edits to a temporary view. Each edit binds a unique
policy/field and its original hash. Missing or ambiguous targets, stale hashes,
protected fields and empty required text reject the complete patch. Text edits
are not evidence of semantic equivalence; promotion needs independent task tests.

The upstream package is pinned at
[`343db229dbd5ddaf9df6b1d5540d8bcdb2604d5c`](https://github.com/microsoft/SkillOpt/tree/343db229dbd5ddaf9df6b1d5540d8bcdb2604d5c).
Its MIT license, original code and per-file provenance are retained in
`third_party/skillopt/`. UPG directly executes upstream reflection, aggregation,
edit selection and patch application through a bounded backend. Third-party
code does not ship inside the ordinary Skill.

## Joint search

- SkillOpt learns limited textual patches from scored development rollouts.
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
python -m evolution run --spec evolution/protocol/upg-evolution.json --output eval-workspaces/evolution/run.json
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

The development spec is `evolution/protocol/rc18-native-development.json`:

```bash
python -m evolution ablate --spec evolution/protocol/rc18-native-development.json --output eval-workspaces/evolution/rc18-native-matrix --runner evolution.native_codex:runner --backend evolution.native_codex:backend
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
Operator-removal controls use `--disable skillopt|annealing|de|curvature`;
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

Current candidate validation and real measurements are pending in
`PROJECT_STATE.md`; the RC17 audit retains its original engineering-only scope.
The planned eight-pair development artifact comparison cannot satisfy the
independent final-evidence or formal qualification contract. No qualifying locked
trial has run, and formal promotion remains BLOCKED.
