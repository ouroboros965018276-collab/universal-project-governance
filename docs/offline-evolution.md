# Offline governance evolution

RC17 adds a repository-only optimizer around the compiled UPG runtime. The
installed Skill still needs no model backend and its optional helpers support
Python 3.8+. Evolution needs Python 3.10+ with current security patches (historical
baseline extraction requires 3.10.12+) and uses the standard library; it never
installs a model SDK or reads account credentials implicitly.

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
Call, token, elapsed-time and candidate budgets bound the controller. Failed
calls and retries consume the same shared budget; unknown provider totals block
further calls. Backends must honor supplied completion limits and perform one
attempt per invocation; they must not hide retries or unmetered work.

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

Checkpoints use atomic same-volume replacement and bind source, engine, vendor,
protocol and callback identities. A callback interrupted in flight leaves a
pending receipt; resume rejects it until independently reconciled. Exclusive
writer locks prevent concurrent use of one checkpoint; a lock left by a killed
process needs explicit recovery. Model and
task outputs stay in the ignored experiment workspace, outside user projects.

## Independent admission

`ablate` executes all nine registered arms, including actual RC15/RC16 Git
archives, with resumable per-arm ledgers. Removing modules reallocates search
rounds to remaining modules under the same overall caps. Unused budget stays
visible; identical caps do not prove identical actual consumption. The matrix is
a development comparison, not independent final evidence.

`evolution/protocol/upg-evolution.json` fixes RC15 as the primary historical
baseline and records RC16 as the latest pre-upgrade regression baseline. It
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

Current engineering evidence and outstanding empirical requirements are tracked
in `PROJECT_STATE.md` and the RC17 audit. No registered final trial has begun.
