# Offline evolution evidence contract

## Prospective real-engineering topology

`evolution.engineering_study.EngineeringStudy` is the maintained, pure-value
contract for the six-condition engineering topology. It does not collect calls,
load private fixtures, authorize dispatch, or replace independent evaluation.
The old `context_campaign.collect` and all frozen study sources keep their
original contracts.

One `real-engineering-six-condition-preregistration-v1` object contains:

- `study_id`, `reviewed_model_delta_id`, exact baseline/full model digests and the reviewed profile digest;
- `condition_bindings`, keyed by `rc19`, `attention`, `full` and the three
  canonical `context_campaign.ABLATIONS` keys. Each binds `model_sha256`,
  `source_sha256`, `runtime_sha256` and `skill_sha256`;
- four `families` in route order: DeepSeek single, MiMo single, DeepSeek to
  MiMo natural handoff, MiMo to native CLI natural handoff. Each contains an
  opaque `family`, `kind`, providers and a complete six-condition `arm_order`;
- the complete `source_pins` map, including `evolution/engineering_study.py`
  and `evolution/context_campaign.py`.

Construct the contract with already authenticated `baseline_model`, `full_model`,
`configuration` and `consumed_source_pins` buffers. RC19/attention share the same
model and asset bindings; attention appends only `ATTENTION_INSTRUCTION`.
`condition_models()` derives each ablation with `trusted_arm_models`. The fixed
RC19 baseline is Git `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9`, canonical model
SHA `44e7d9fd...`. Delta `rc19-bd4-to-rc20-reviewed-evidence-closure-and-guidance-v1`
admits only the reviewed version/guidance additions (including the exact pinned
`operational_guidance`) and the fixed `EVIDENCE_AFFECTED.closure` upgrade that
requires negative, exceptional and combined boundary checks at affected high-risk
boundaries. Every other model/core-policy field is compared exactly: all policy
IDs, hot-path IDs, severity, triggers, requires, conflicts, report and safety
obligations remain intact. Future core changes require a separately reviewed
delta version; the optimizer cannot supply one. Asset digests do not prove that a
compiler rendered those models: retain the existing compiler/runtime checks.

The derived plan has 24 workflows, 36 roles (30 API, 6 native CLI), 720 API request
slots, 1152 tool slots and six private panels of six roles. The unchanged envelope
is 600 work seconds, 24 API requests, 32 tools and profile `0d204c60...`; accounting
settlement/cleanup and publication allowances give a 41250-second conservative
outer envelope. These are reservations, not usage, prices or performance claims.

For a new candidate source, use these existing responsibility seams:

| Consumer | Contract projection |
| --- | --- |
| `study_contract` / source admission | `fixed_order()`, `fixed_registry()`, `counts()`, `registry_identity()`, `caps()`; `validate_protocol()` checks the complete bound identity and order. |
| `field_adapter.registry_bindings` | `fixture_bindings()` supplies the family/stage map from preregistration, without loading task bodies. |
| `fixture_interface` | Call `validate_family_stage()` instead of maintaining another opaque-family allowlist. Preserve every other field, path, backend, receiver and scope check. |
| `managed_contract` | Only an explicitly selected new topology branch uses `validate_registry()`. Keep the old strict default; retain configuration, deadlines, settlement, accounting and safety predicates. Compare its derived reservation counts to `caps()`; retain existing separate API/native accounting and pricing. |
| Owner-only manual preparation | `private_panel_assignment()` derives all panels and the 36-role lock denominator before any unblinding. |

Authenticate the new module and preregistration through the existing source-map
loader and include both identities in prospective bindings. A hash comparison
inside this pure module is not proof that a caller consumed the actual files.
No frozen source is updated by this contract. Existing collector, owner, reader,
manual and analysis sources still have old arm/count literals; they must be
adapted and independently checked in a new candidate before a complete runner is
ready. Preserve accepted-source handoff gates and every planned-role failure or
UNINVOKED outcome. Fresh IDs alone do not establish unseen private projects.

`upg-evolution.json` is the registered objective and constraint surface. Search
operators do not edit it. The optimizer searches canonical model prose and legal
presentation parameters; its control parameters stay outside the runtime.

The fixed primary baseline is RC15 commit
`0808842e759763c722f77a2fd9b464842480a290`. The separate current-release baseline
is RC16 commit `9c0efc1165a0e648622d8a4c02c2b1ddbd4986fb`. Engineering matrix
baselines use exact Git archives and historical compilers/runtimes. Byte counts
are development objectives, not measurements of tokens or product effectiveness.

## Execution and independent evaluation

`run` uses development tasks only. `ablate` executes all registered arms with
identical total search caps; removed-module dispatches are reassigned by the
controller. Actual spending can differ. The matrix reports this distinction and
does not assert conditional contribution or empirical savings.

Promotion additionally requires a separate, independently operated holdout
evaluation. The run refers to its manifest with:

```json
{"independent_evidence": {"path": "holdout/manifest.json", "sha256": "SHA256 of exact file bytes"}}
```

Artifact references use `path` and the SHA256 of exact file bytes. Relative paths
resolve against the containing artifact. Structured artifacts are JSON objects.
Hashes detect changes; they do not authenticate an external provider or grader.
The independent evaluator and its provider evidence are a documented trust
boundary, not an authority that can be manufactured by setting a pass flag.

The manifest contains `freeze`, `records`, and `optimization_calls`. `freeze`
has `git_revision`, repository-relative `path`, and `sha256`. It refers to a
freeze document committed in this repository **before** final observations:

- `kind: "independent-holdout-freeze"`, `run_id`, selected `candidate_id`,
  `candidate_source_sha256`, `protocol_sha256`, `source_sha256`, and
  `engine_sha256`, all bound to the actual run and current executable source.
- Distinct `optimizer_actor` and `independent_actor`; timezone-qualified
  `selected_at` and `frozen_at`. Selection precedes freezing; observations follow
  the actual anchor commit's committer timestamp.
- `baseline_revisions` with `rc15` and `latest_baseline` equal to registered
  full Git revisions. Both Git objects must be available.
- `splits.training`, `splits.selection`, and `splits.final`, each a nonempty array
  of `{task_id, task_family, project_id}`. IDs, families, and projects are
  disjoint between splits. Final handoff entries additionally use
  `kind: "handoff"`. `prior_final_task_ids` records previously exposed tasks;
  they cannot be reused for another final evaluation after feedback.
- Normalized positive `model_family_weights` and `task_family_weights`, fixed
  before observations; `arm_budgets` with identical caps for every search arm.
- `grader: {path, sha256}` pins the independent grader's source in the same
  anchor commit. Grades must bind that source hash.

Each referenced observation in `records` must be a `real_model_task`, a fresh
independent sample, and explicitly a cache miss. It binds `observation_id`,
`pair_id`, `arm`, `candidate_id`, `source_sha256`, `source_revision` for historical
baselines, `protocol_sha256`, task/project/family IDs, model family/model ID,
configuration/dependency hashes, runner ID/version, `started_at`, actual
`wall_seconds`, `usage`, and the complete ordered `attempts` list.

Each attempt records `attempt`, `status` (`completed` or `failed`), actual
`usage`, and a `provider_receipt` reference. Receipts contain
`kind: "provider-usage"`, `provider`, unique `request_id`, `model_id`,
`observed_at`, and actual provider `usage`. The aggregate total must include every
failed and retried call. Unavailable cached/reasoning/currency fields stay null;
missing total tokens prevent promotion. One provider request cannot be reused
across observations or any optimization/control arm.

Observations also reference:

- `context_receipt`: `kind: "context-token-measurement"`, the candidate ID,
  actual `token_count`, and `tokenizer_id`.
- `timing_receipt`: `kind: "task-timing"`, `clock: "monotonic"`, the observation
  ID, and measured `elapsed_seconds` matching the observation.
- `grade`: `kind: "executable-task-grade"`, observation ID, frozen
  `grader_sha256`, numeric `quality_score` in 0..1, positive
  `core_requirements_total`, `core_requirements_met`, `critical_failures`, and
  hashed task-output `artifacts`. Manual pass booleans are not quality evidence.

`optimization_calls` maps every search arm to actual provider-receipt references,
including reflection, aggregation, ranking, failed calls, and retries. These
receipts additionally contain measured `wall_seconds`; known dollar costs are
reported separately. Actual full-system calls/tokens cannot exceed a comparison
arm's spending. All frozen caps still apply. The run must contain evaluated
candidate provenance for all four operators.

## Computed gates and limits

The verifier recomputes paired metrics from artifacts, using the registered
model/task-family weights and deterministic paired bootstrap. Task families and
pairs are resampled; model families are reported individually and aggregated
with their frozen weights. Required coverage includes three model families,
twelve task families, six handoff families, and eight independent repetitions
per family cell. All registered baseline/control/ablation arms must be present.

Full-system quality must be noninferior overall and within each model family;
core requirements and critical safety failures cannot regress. Against both
historical baselines, context tokens must fall at least 25%, full-task token ratio
must be at most 0.85, and wall-time ratio at most 0.90, with cost-ratio 95% interval
upper bounds below one. Equal-budget controls/ablations must establish their
conditional cost contribution; negative or uncertain results remain blockers.

Optimization cost and reliable per-task savings yield separate token, time, and
money break-even estimates. Missing monetary evidence stays unknown. A positive
mean without a positive lower confidence bound does not establish break-even.

`verify` independently reports engineering, empirical, and formal-qualification
status. `propose` creates a new review directory containing a source patch,
compiled runtime, selected model, and verification result only after the
independent gates pass. It never modifies canonical source or grants formal
qualification. Without valid locked observations, empirical status is
`BLOCKED`; numerical/unit-test fixtures and development matrices cannot satisfy
this gate.
