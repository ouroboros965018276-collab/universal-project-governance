# Project State

Current candidate: **3.0.0-rc.19 — Project Fact Recovery and Measured Execution Cost**.

## RC19 current development checkpoint

The completed [v10 tool comparison](docs/rc19-tools-development-v10.md) retains
32 fresh calls and 2,571,232 reported tokens without unknown usage. Independent
raw/statistical audit passed: treatment quality 16/16, control 15/16; tokens
fell 5.4389% with both registered interval upper bounds below one, while callback
time increased 0.6230% and both requested model timing points regressed. The
unchanged net-benefit gate remains FAIL. Cumulative known usage is 353 completed
turns / 12,028,747 tokens, plus four unknown dispatches (357 actual CLI calls).

Source `ff30c8a8f93b6bc12214bd5c73a875efb44b28c1` passed hosted PR run
38307551411, all 11 jobs including both real Skill loaders; Windows discovered
510 tests and passed, while Python 3.8 passed 263 with 247 skips. This validates
that committed source rather than later text changes.

The [cost diagnosis](docs/rc19-tools-v10-cost-diagnosis.md) supports a narrow
clarification: dependent after-state checksums can use verified edit receipts
and still-current reads. Content/contract inspection and all stale/missing/
failed/later-edit exceptions remain mandatory when applicable. This single
canonical clause was independently reviewed, compiled into an 8,303-byte Skill,
and passed eight local gates under freeze
`eb2312969d63541c4269ab9afc386c5673466f863465ef84beaa66b3b96aa9d1`.
It does not establish performance benefit. A new focused development v11 will
cover four exposed recovery tasks on both requested models (16 fresh calls).
The sealed six-family final B, original statistical/quality gates, default
main RC18, global installed RC18 and all old unknown fences remain unchanged.
Native preparation is repository-only and cannot be inserted into installed
Skill timing or combined retrospectively with v10 to claim joint benefit.

## Preceding RC19 recovery checkpoint

Observed worktree HEAD is `9bf5e97693b225c87a6fab2af9b96fb5aed1f0b6`.
Default `main` remains accepted RC18 at
`29cf112b4629d6b90504b079e95a5370c206a4cb`, and the global installed Skill remains
RC18. RC19 is active and unfinished; no merge or local promotion has occurred.

The independently audited [native A5](docs/rc19-native-independent-a-v5.md) and
[nine-arm development](docs/rc19-nine-native-development-v2.md) evidence was
committed at `3ea`. A5 retained 32 fresh strict passes and 439,193 reported tokens;
its full-callback time/quality gate passed, with ratio 0.785054 and 95% joint
family-block interval [0.761984, 0.808256]. Its token interval crosses one and
Luna tokens regress 1.2071%; A5 does not establish joint token/time benefit or
relax Tool B gates. Nine-arm development retained 209 known turns and 3,302,409
tokens, with no distinct or selected edits; empirical admission is BLOCKED and
contribution/token/time-benefit claims remain unassessed.

The [child-route v3 diagnostic](docs/rc19-child-route-v3.md) has independently
reconciled evidence, with its new docs/audit still uncommitted at this checkpoint.
Sol completed both tiny public tasks with 20,122 reported tokens; Luna's
child-no-proxy call returned `Connection failed: error sending request` without
completed usage. The fourth call was not dispatched. The unknown fence remains,
and NO_PROXY has not been adopted. This is diagnostic evidence, not a routing,
latency or reliability improvement. Cumulative RC19 accounting is **321 known
completed CLI turns / 9,457,515 known reported tokens plus four unknown-usage
dispatches: 325 actual CLI dispatches**. This includes the prior v2 known strict
failure; A4's worker reservation had zero actual CLI dispatches and is excluded.

Compact wording was adopted with unchanged model, eight HotPath items and sixteen
policies. Its 8,172-byte form at `3ea` had an unquoted `: ` in the description;
hosted CI at `9bf5e97` passed 9/11 jobs and both external Skill loaders rejected
that YAML scalar. The current candidate uses a plain description with template
SHA-256 `9248ce28b78103f9b8fa2dde485fc1ebd77c1d6bbc2d290db6ee620303ae9648`;
the actual generated Skill is **8,180 bytes**. Six frontmatter regressions passed
independently and all eight release checks passed. Two initial check preparations
failed because TEMP was not redirected from the sandbox path; their receipts are
retained, and the two checks passed with the correct project TEMP. These results
do not replace external loader validation, which awaits the next pushed source.
See the [frontmatter compatibility audit](audits/rc19-frontmatter-compatibility.audit.json).

Development v9 made zero model calls because CI blocked it; its old registration
remains unchanged. The v10 driver is SOURCE READY only, has not prepared a new
protocol and has made no model calls. Next: commit the corrected source/evidence,
obtain hosted loader acceptance, then create and review a fresh v10 freeze before
any development dispatch. Sealed Tool B remains unexposed and uncalled. Preserve
all original protocols, scores, costs and unknown fences; do not replay them or
use final-task feedback for tuning. Formal qualification remains UNASSESSED.

## Historical RC19 preparation and measurement checkpoints

The default branch contains RC18 through PR #19, merge
`29cf112b4629d6b90504b079e95a5370c206a4cb`; local RC18 installation was accepted.
RC19 investigates the reported 23.6975% callback-time increase and prepares a
new frozen comparison on two catalog-observed OpenAI models with actual bounded
repository tools. [Diagnosis](docs/rc19-latency-diagnosis.md) records one tail
pair contributing 95.74% of the historical increase and reproduced redundant
binary hashing/compilation. Local warm preparation improves; new independent
model token/time benefit remains pending. Formal qualification is UNASSESSED.
Historical source, frozen measurements and unresolved limits below remain intact.

The first [RC19 development transport](docs/rc19-tools-development-v1.md)
completed eight known paid CLI turns using 208596 tokens, but the disabled
Code Mode host prevented every tool call. Task quality was 0/8 and benefit
admission failed. Original records and costs are retained; the pre-call
`rc19-latency-tools.audit.json` is a historical preparation snapshot.
No RC19 final independent calls, default-branch merge or local deployment have
occurred at this checkpoint. The child transport is being corrected before
a separately frozen development probe.

The [two-call transport probe](docs/rc19-tools-transport-v2.md) subsequently
confirmed both actual CLI host process paths and retained another 75349 tokens.
Its registered MCP attempts were denied by the child's approval configuration;
broker executions and passing tasks remained zero. The ten known failed turns
therefore cost 283945 tokens in total, with no efficacy claim. A new child
profile explicitly preapproves only the five authorized broker tools and keeps
the global approval policy and native tool restrictions. Its separately frozen
development probe must establish useful tool execution before final testing.

The [v3 transport probe](docs/rc19-tools-transport-v3.md) subsequently passed
2/2 tasks and all four positive checks, with 11 independently reconciled real
broker calls and both registered host paths observed. Its one-family development
scope does not establish efficiency; the unchanged coverage gate correctly fails.
The three rounds total 12 known turns and 431713 tokens. A separately frozen
16-turn development comparison now covers four known task families on
`gpt-6-luna` and `gpt-6.1-sol`. Final instances remain unexposed to the models;
they have distinct initial files and expected checks, while sharing these four
task families, generic prompt templates and the protected NOTICE sentinel.

The complete two-model development comparison subsequently passed 16/16 tasks,
using 1344852 reported tokens and 102 broker requests (95 successful operations
and seven recovered, correctly denied reads outside the registered path set).
Its token point estimate
was 3.6469% lower, but full callback time was 9.3737% higher; both 95% ratio
intervals crossed one. Both model timing point estimates regressed. The unchanged
net-benefit gate failed, so final tasks remain unstarted. Known RC19 rounds now
total 28 turns and 1776565 tokens, including the ten failed transport turns.
The next development candidate makes evidence reuse and batched inspection
explicit, while preserving all policy/plan semantics. Hosted CI also exposed a
terminal-budget snapshot mismatch: the collector now synchronizes its saved
summary to the same advancing clock snapshot and blocks benefit if final summary
work crosses the wall threshold. Historical experiment records are not rewritten.

The [v4 development audit](docs/rc19-tools-development-v4.md) retains another
16 completed calls and 1078496 tokens. All 32 positive artifact checks and all
76 broker operations passed, but four calls contained transport errors, so strict
task quality was 12/16. Token use fell 2.8023% with a ratio interval below one;
callback time fell 6.1966% as a point estimate, but its interval crossed one and
one model regressed slightly. Net admission therefore remains FAIL. The five
RC19 rounds total 44 completed calls and 2855061 reported tokens; independent
final tasks remain uncalled and the installed Skill remains accepted RC18.

A prospective shared child HTTP profile is now being prepared for both arms.
The matching official CLI loaded its provider configuration and retained the
existing ChatGPT login in read-only RPC checks. No inference was performed in
that check. This addresses the newly observed TLS/WebSocket errors, whose
relation to the historical RC18 tail remains unknown. A separate artifact-grader
repair rejects duplicate JSON keys, non-finite numbers and Python's bool/int
equality ambiguity. It applies to new trials, not retrospective regrading.

The new prospective [uncertainty registration](evolution/protocol/rc19-joint-family-uncertainty-v1.json)
also requires joint task-family intervals preserving both requested models,
in addition to every original acceptance gate. Four known families remain four
independent blocks, regardless of model or instance count. A separately published
[native callback collector](docs/evolution/native-paired-campaign.md) measures
actual public-entry preparation, CLI and evidence costs in persistent matched
workers; it has performed no inference at this checkpoint.

**Owner-resumed RC19, client date 2026-10-13.** The [v5 partial audit](docs/rc19-tools-development-v5.md)
retains six completed calls with 407496 reported tokens, 12/12 artifact checks
and 5/6 strict admissions. The seventh dispatch returned model-capacity failure
without completed usage; its unknown-call fence remains and it was not replayed.
RC19 totals are 50 completed calls / 3262557 reported tokens plus one additional
unknown-usage dispatch. Net benefit remains FAIL. Native A and independent final
tool calls remain zero; default main and the accepted local RC18 Skill are unchanged.
The previously paused model/protocol parameterization is independently reviewed;
Windows aliases and trailing dots are rejected. New ordinary request, stream and
unbounded-connection retry suppression is shared and hash-bound across arms;
authentication recovery and failed partial-response billing remain explicit limits.
Project fact recovery reuses the current handoff, explicit file scopes, positive
source-state checks and static/dynamic validity distinctions. Native reflection
replaces the executable third-party dependency. Source backups and historical
license/provenance remain recoverable. Full regression, new protocol freezes and
independent net-benefit measurement remain required before integration/deployment.

Candidate source `60c8b0f44d7290f15e92a45de346be1c7d0a0aea` now passes
473 tests (471 executed passes, two Windows link-privilege skips) and all eight
release checks. Two package builds match SHA256
`bc245bfc3af5e6a01149f8825f03631b5bed63e974bace31cd2353f250100e7f`.
The runtime contains 18 files; its Skill is 8843 bytes versus RC18's 7940.
No byte-saving claim is made. Native reflection and recovery received independent
source review, including the repaired Git clean-filter execution boundary.

The [fresh v6 recovery probe](docs/rc19-capability-recovery-v6.md) completed four
new calls on requested `gpt-6-sol` and `gpt-6-luna`: strict quality 4/4,
12/12 positive checks, 28 real tools, 424417 reported tokens. Pooled token point
improves 7.84%; callback time improves only 0.24%, with Sol time regressing
2.43%. Net benefit remains FAIL. Cumulative metered RC19 experiments now have
54 completed turns / 3686974 reported tokens plus one preserved unknown dispatch.
Development conversation and subagent usage are not included in those totals.
The next six-family development protocol and independent native A v2 protocol
are preregistered at `cf9f5dcd2c227a2717c303d4f4acacd8bbfb91d1`; neither has
dispatched a model at this checkpoint. Independent tool fixtures remain sealed.

Hosted CI for `5f57df8ac1dd667e8764b39b0a781478aaed0056` subsequently passed
8/11 jobs. Python 3.8 exposed an optional offline-test version boundary;
Windows 3.11 and 3.13 exposed a real reference-identity bug. Safe references now
use canonical paths after link/reparse/hardlink rejection, preserving evidence
through short-path and lexical directory aliases. Native offline tests explicitly
require Python 3.10+, while installed helpers retain Python 3.8+ support.
Local regression after these changes ran 477 tests (475 passes, two actual
link-privilege skips), with all eight release checks passing. Hosted verification
of the corrected source remains pending. Uncalled development v6 and native A v2
are retained; corrected-source development v7 and native A v3 require new freezes.
These engineering fixes establish no additional model efficiency result.

The corrected source `38d469126fb31e4572689a5934d0bac2b9a470cd` and public freeze
`5b28efb6a4ab522da855a217d8de14d2c6b739ac` now have independently observed
[PR](https://github.com/ouroboros965018276-collab/universal-project-governance/actions/runs/38286771981)
and [push](https://github.com/ouroboros965018276-collab/universal-project-governance/actions/runs/38286766579)
CI success, 11/11 jobs each. Python 3.8 discovered 477 tests with 230 skips
and 247 executed passes; PR Windows 3.13 passed all 477 in 71.716 seconds,
including real short-root retention. These hosted runs are separate from the
local full suite before the final test-bootstrap edit and the final 17-test
standalone focus; their counts are not summed.

The [v7 partial audit](docs/rc19-tools-development-v7.md) retains seven completed
turns / 668208 reported tokens, all seven strict passes and 16/16 positive checks.
The eighth dispatch made four real tools and two partial edits, then failed with
`Connection failed: error sending request` without completed usage. Its network
root cause remains unknown; the pending/unknown-call fence is preserved without
replay. Net benefit remains FAIL and formal qualification UNASSESSED. Cumulative
RC19 accounting is 61 completed known-usage turns / 4355182 reported tokens plus
two unknown-usage dispatches (63 dispatches total); missing usage is not zero.
Independent native A3 and sealed Tool B final calls remain zero. Earlier uncalled
v6/A2 freezes and the separate v5 unknown fence remain unchanged; default main
and the accepted local RC18 Skill have not been promoted by this partial result.

The next [engineering preflight](audits/rc19-observed-receipts-preflight.audit.json)
adds safe actual-byte patch hashes to the common tool scaffold, retaining all
initial-read, scope and current validation/status gates. The Skill makes the
smallest read/change/verify sequence explicit. Native completed-turn costs now
survive raw/result/receipt persistence failures; unresolved evidence retains the
original dispatch lock, including a lost receipt acknowledgement followed by
both fence-write failures. Independent fault-injection reviews passed; no real
call was replayed to test these failures.

Local full regression passed 499 discovered tests (497 executed passes, two
link-privilege skips) and eight release checks before the final two-line lock
correction and its additional regression. Final native focus passed 41/41 and
paired focus 30/30, with an independent 13/13 cost focus and combined-fault
reproduction; these overlap the full suite. Final 500-test hosted verification
is pending. Two actual package builds match
`da2b98c2eb95ba209d8d29f3caca761073e08fbe1e4b3bea81df5d3c957f4b70`.
The 18-file runtime Skill is 8814 bytes, still larger than RC18's 7940.
There are no new model results or efficiency claims for this candidate. New v8,
native A4 and nine-arm development registrations are required before dispatch.

At source `0bd647a79a7270c674238916217385c4e749a399`, hosted PR verification
[run 38292522683](https://github.com/ouroboros965018276-collab/universal-project-governance/actions/runs/38292522683)
passed 11/11 jobs, including all 500 tests on Windows Python 3.13 and the
Python 3.8 compatibility discovery (257 executed passes, 243 skips).
The [v8 capability probe](docs/rc19-tools-capability-recovery-v8.md) passed four
strict tool tasks: token/time points improved 16.4199%/12.4302%, but its one-family
scope fails the unchanged independent net-benefit gate. The subsequent
[v8 development collection](docs/rc19-tools-development-v8.md) stopped after
twelve strict passing completed turns and an unknown-usage connection failure.
Its completed prefix regressed 4.9995% in tokens and 1.7636% in callback time;
these incomplete diagnostic points establish no benefit. Retained actual CLI
totals are 77 completed turns / 5685732 known reported tokens plus three unknown
dispatches. Provider invoices and failed-partial usage remain unobserved.

The newly attempted independent A4 collector stopped at its first worker input
validation with a Windows Unicode decoding error, before the native callback.
Its original reservation, pending state and raw worker logs are retained for
independent reconciliation; no result is admitted as model evidence. A separately
frozen encoding correction is required. Nine-arm native development and sealed
Tool B have no new dispatches. Default main and the installed Skill remain RC18;
neither the passing engineering checks nor the development probe authorize
promotion without the required independent token/time/quality evidence.

Independent [A4 reconciliation](docs/rc19-native-independent-a-v4.md) confirmed
zero actual CLI entries before the failed input digest. The corrected strict
ASCII JSONL wire passed 34 focused tests, including three real CP936 Python
subprocess canaries; an independent run passed the four new cases. Source,
digest, callback timing, grading and CLI argument semantics are preserved.
The next cost-guidance candidate batches known source/consumer/contract/evidence/
state reads and derives records from verified writes and unchanged current
reads. Its 8807-byte Skill is seven bytes smaller than the v8 candidate; this
is not token-benefit evidence. Policies and Hot Path are identical, all eight
release checks pass, and the new qualification fingerprint is
`sha256:10f15583bd1c3d7bcfd2168d6f751eac015b3aa421f37afbbef22f829cec965a`.
New source-bound native and tool experiments are required before any promotion.

The [A5 independent audit](docs/rc19-native-independent-a-v5.md) subsequently
confirmed 32/32 fresh strict passes and 439193 reported tokens. Full callback
time fell 21.4946%, with joint-family ratio interval [0.761984, 0.808256].
Token benefit was not established: its interval crossed one and requested Luna
regressed 1.2071%. All warnings, the unexplained first Sol control token excess
and host-load limitations remain recorded. A5 applies to source `1f286516...`;
it cannot substitute for independent Tool B evidence or certify later text edits.

The [native nine-arm audit](docs/rc19-nine-native-development-v2.md) independently
reconciled 209 real calls: 173 passing task turns and 36 learner turns, using
3302409 reported tokens without unknown calls. All nine arms completed under
equal ceilings. The learner proposed zero distinct edits; accepted search
steps do not establish causal value. Empirical admission remains BLOCKED,
formal qualification UNASSESSED, and savings/contributions null.

A [bounded route diagnostic](audits/rc19-child-route-v2.audit.json) then stopped
after one known 10059-token completion: the fixed JSON was correct but two CLI
startup errors failed strict admission. No alternate-route call occurred and
no network conclusion follows. Its original failed record and fence remain.
Cumulative actual CLI accounting is 319 known completed turns / 9437393 reported
tokens plus three unknown-usage dispatches; A4's pre-CLI reservation is excluded.

The next reviewed wording candidate compiles to 8172 bytes / 79 Skill lines.
It restores explicit preservation of all existing settings and ledger, retains
16 policies / eight identical Hot Path invariants and passes all eight release
checks. New qualification fingerprint:
`sha256:9226a53376140b3cd2f3acd9a6adce35bf895b7fe808371889be98e766fdf50c`.
This text-size change is not measured token/time benefit. Hosted PR
[run 38303104830](https://github.com/ouroboros965018276-collab/universal-project-governance/actions/runs/38303104830)
passed all 11 jobs for the preceding committed candidate, including 504/504
Windows Python 3.13 tests and 257 executed Python 3.8 passes / 247 skips.
New source-bound tool testing and independent net admission remain required;
default main and the installed Skill remain RC18.

## RC18 candidate — paired measurements and nine-arm matrix completed

The default branch already contains RC17 through [PR #18](https://github.com/ouroboros965018276-collab/universal-project-governance/pull/18), merge `e63f438bdee2b9d65c49db6c621e968d6b185e56`. RC18 continues from that release. The prior RC17/RC16 records below describe their original stages; their test counts, failures, unknowns and qualification outcomes are retained.

This candidate repairs three reproduced grader false positives: an emptied refactor module, removal of the required database driver from both dependency files, and an interoperability no-op. Checks now require bounded pure-function behavior, exact complete dependency targets, and the implementation/documentation change respectively. Diagnosed development and locked labs are exposed regression fixtures; they cannot establish a new independent holdout result. Generated model code is not executed by these probes.

The canonical Skill template is compacted while preserving its obligations and Hot Path. Compiled `SKILL.md` shrinks from 11144 to 7940 UTF-8 bytes, a 28.75% reduction; these bytes are distinct from the observed prompt-token reduction below. Three runtime helpers accept UTF-8 JSON with a BOM. Native-CLI development callbacks bind configuration, binary, grader, canonical source and compiler; selection caps and replayed learning accounting belong to the same budget boundary.

The [paired artifact summary](qualification/pilots/rc18-native/paired.summary.json) records eight prespecified RC17/candidate task pairs at source `e08faff3c37bb2736e387a5ca743b3b20644f9dd`: 16 fresh calls, all positive task checks passing, 216759 completed-turn tokens in total. Input tokens fall from 109950 to 105715 (3.85175%); total tokens fall from 110504 to 106255 (3.84511%). Full evaluator callback time, including isolated compilation, planning and grading, rises from 70.98168 to 87.80255 seconds (point estimate +23.6975%); its ratio 1.23697 has a paired-family bootstrap 95% interval of [0.95923, 1.51345]. No timing improvement is established. This is bounded artifact-task evidence in one requested model, without a causal operator-contribution or generalization claim.

The [v1 round summary](qualification/pilots/rc18-native/round-v1.summary.json) retains 39 completed-turn calls and 553938 tokens, including the 16 paired calls above. Its development matrix stopped in the full arm with `SourceBridgeError`: an invalid learner edit was safely rejected, but the controller wrongly aborted the arm; five arms did not run. Original checkpoints and costs are preserved. After repairing charged invalid-proposal handling, the [fresh v2 nine-arm protocol](evolution/protocol/rc18-native-development-v2.json) completed 9/9 arms and passed independent audit of the experiment records. Its 188 actual CLI turns comprise 158 task calls and 30 learner calls, consuming 2684192 tokens. All 158 raw task results pass mechanical regrading; final-task dispatch is 0. This establishes the bounded development execution, without a causal algorithm-benefit claim.

Two Windows checkpoint `Path.replace` operations were temporarily denied during v2. Each recovery reconciled already charged calls before resuming the same frozen protocol and engine; additional calls are included in the shared budgets and totals. The occupying process and specific cause remain unconfirmed. Repository-only bounded checkpoint-I/O retry hardening was added after measurement, without changing the runtime, algorithm or protocol. Final local regression passes 299/299 tests in 98.700 seconds and all eight local release gates pass. The measured v2 engine SHA-256 is `a4cccff429ac43ee062859ee494b5378492efabef89f56a1ac8ac4780ee7bf1e`; the release engine is `1d113d87c50641b4d35de00a366cb15438b5a6489cbe6b3789dd955698512acd`. Measured evidence is not rebound to the repaired release engine. Runtime Skill and task grader remain those of the paired tested revision, and final-task feedback is not reused. See the [real-evaluation report](qualification/pilots/rc18-native/README.md) and [release audit](audits/rc18-real-evaluation.audit.json); hosted CI passes 11/11 at measured freeze `8d1cb51945c5d98bf3db7c2e72557d7e50274275`, with final PR/main CI recorded separately. Requested `gpt-6-luna` identity is not yet provider-confirmed; native provider-internal retry usage coverage remains unknown. JSON artifact repair covers neither actual tool execution nor a complete cross-Agent handoff.

| Cost scope | Actual CLI turns | Reported tokens |
|---|---:|---:|
| v1, including the 16 paired calls / 216759 tokens | 39 | 553938 |
| v2 nine-arm development round | 188 | 2684192 |
| Trials subtotal | 227 | 3238130 |
| Separate capability probe | 1 | 14921 |
| Total including probe | 228 | 3253051 |

Pre-merge installation snapshot: the user-level Skill is RC17, with a recoverable RC16 backup, all 17 bundle files matching that compiled release, passing runtime integrity, matching planner output in eight fixture contexts, and one enabled UPG entry found by a fresh official CLI process with forced reload and no discovery errors. This establishes disk/helper behavior and host discovery, not historical or causal model activation. RC18's package and recoverable RC17 backup are prepared but not installed at this snapshot; installation follows candidate verification, measured-outcome review and default-branch integration. Later deployment must retain its own observed acceptance record. The prior ignored RC17 trial-copy cleanup exception remains a separately retained observation.

Independent empirical admission remains BLOCKED and formal qualification is UNASSESSED. No learned candidate is promoted. Locked qualification is NOT RUN; empirical qualification and Stable are NOT ACHIEVED. Thresholds and completed historical result rounds are unchanged. Current development measurements cannot replace the required independent model-family, task-family, isolation, safety, cost and handoff evidence.

Final release-only I/O review also repaired the controller's outer exception path: a persistent checkpoint replacement failure propagates without a second `save_run`, preserving the same six-attempt bound and complete temporary bytes. The focused I/O suite passes 46 tests, including seven added methods covering 12 fault scenarios; independent read-only code review passes. This does not alter the measured engine, canonical governance, installed runtime, task grader or protocol.

## RC17 historical implementation stage

The following record is retained from the RC17 implementation stage, before its later merge and the explicit user-level installation recorded above.

The upgrade starts from remote main `272861ab9d925e7943fd84cbd6ff210bdb68841d` and integrates the latest public RC16 candidate `9c0efc1165a0e648622d8a4c02c2b1ddbd4986fb` through merge `24ad60309f01e787c2cedb1c258ac8e517e6a953`. The original RC12 checkout and its uncommitted adapter changes are preserved outside this worktree.

RC17 directly reuses pinned MIT SkillOpt code and adds a hash-bound source bridge, shared budgets, deterministic checkpoints, chaotic annealing, adaptive differential evolution, trusted negative-curvature proposals, real-task/selection adapters, independent evidence admission and a nine-arm development matrix. Legal presentation parameters can reorder required closures and evidence, while mandatory rules, dependency closure, safety, reporting and handoff requirements remain intact. The optimizer stays outside the installable runtime and adds no daily model calls or project-managed files.

Final local engineering validation passed: 214/214 tests on Windows Python 3.12.10 and all eight static/release gates. Two deterministic packages match SHA-256 `1683cd8c709c7925fa9c5a22b39d85a82308bfaefca6283799fc2304292ae90e`. The three-round search checked 60 unique executable candidates; the nine-arm development smoke completed, including exact RC15/RC16 historical baselines. The best fixture context-byte objective equals the baseline (12728.25): no improvement was observed. See the [RC17 audit](audits/rc17-offline-evolution.audit.json). Hosted checks and integration are recorded against exact revisions on GitHub.

Source, numerical and development-matrix tests are engineering evidence. No real frozen holdout has run: the existing AI-lab entry has no registered project or usable provider credential. No account settings were changed or login material copied. Context bytes are not token measurements; token/time savings, causal module contribution and break-even remain unknown. Locked qualification remains NOT RUN; empirical qualification and Stable remain NOT ACHIEVED. Promotion rejects missing independent evidence.

An isolated project install verified all 17 RC17 bundle files. Its binding was removed, but Skills CLI 1.7.0 crashes during Windows uninstall; automatic approval review rejected the verified narrow manual deletion with `blocked by policy`, including after renewed owner authorization. The remaining copy is confined to ignored `eval-workspaces/install-rc17/.agents/skills/universal-project-governance`; review/removal is pending resolution of that external restriction.

The user-level installed Skill was RC16 when this task began and was not replaced by this repository upgrade. Existing projects need an explicit install/update from the desired branch. Historical evidence below retains its original version and scope.

## RC16 historical candidate

This candidate is based on the unmerged RC15 branch at public revision `42a72ff7efb0b830b9ef89d79c0cc399baff1b74`. It repairs the independently reproduced finish mismatch and adds optional checked references to one validation truth source. The original RC12 checkout and its unrelated uncommitted adapter changes are outside this task. The prior global RC15 Skill was backed up and all 17 files verified before replacement. The current user-level installation is RC16, its 16-file integrity manifest passes, and all 17 installed bundle files equal the compiled candidate. This verifies current disk state; automatic/historical Skill activation remains unmeasured. No private project repair or historical backfill was performed.

Final local engineering validation passed: 136/136 tests on Windows Python 3.12.10; compiler, lint, qualification/freeze, repository, bundle, integrity and security checks passed. Two packages match SHA-256 `c7c8b448a687a771f2a7da931e33d337966cad166ae2036c84339cacda47ca86`. See the [RC16 audit](audits/rc16-field-feedback.audit.json). The skill-creator quick validator could not start because existing Python runtimes lack PyYAML; the maintained bundle/frontmatter validator passed instead. No tool was reinstalled. Retrospective reports are summarized in [the sanitized feedback](docs/field-feedback/rc16-retrospective.md); supplied test counts and behavior observations are not causal evidence, independent task counts or current reruns.

One independent receiving-subagent synthetic maintenance exercise passed: existing tests2/3 before and3/3 after, shared validation reference reconciled, start facts retained and workflow completed. This same-family diagnostic is not a paired cost or locked handoff trial.

Locked qualification remains NOT RUN; empirical qualification and Stable remain NOT ACHIEVED. Optional host activation receipts, prospective paired token/time/tool costs and real two/three-Agent handoff evidence remain outstanding. The qualification protocol and thresholds are unchanged.

## RC15 historical candidate checkpoint

The top-level installer previously returned the first recursive match for `universal-project-governance/SKILL.md`. A stale copy under an earlier-sorting hidden directory could therefore be selected ahead of Codex's installed project target. A no-model-cost regression reproduced the defect. RC15 changes the Codex lookup to the canonical `.agents/skills/universal-project-governance` path, treats noncanonical copies as preexisting for safe rollback, preserves unique non-Codex lookup, and rejects ambiguous non-Codex copies. Windows Python 3.12 passed 105/105 unit tests; repository, compiler, lint, qualification, freeze, bundle, integrity, and security checks passed. Two deterministic package builds matched SHA-256 `6ac4d1a90ba640c1ec0ac974258cb0a678f0f8e105c348496fa3225e5a627128`. Hosted validation runs on the current branch head of draft [PR #14](https://github.com/ouroboros965018276-collab/universal-project-governance/pull/14); consult the live PR checks for the current result. RC14 evidence below is historical and its fingerprint does not cover this candidate.

At the verified candidate head `0808842e759763c722f77a2fd9b464842480a290`, hosted CI run #250 passed. In this task, `skills.read` resolved the installed Skill under `~/.codex/skills/universal-project-governance` as RC15. Its `SKILL.md` SHA-256 is `2a04056ea0273e4a3474b0be1e2f44e7852c5eba0d7b0472128dfd3d90e84890`, matching the candidate file; the installed and candidate integrity manifest SHA-256 values also match (`02208f5fa2d32a696295b8005fd53eca71eec58639e0f40a6d40e66d3992ba05`). This current-task check is separate from the earlier fresh-task catalog result, which remains unknown.

The RC14 DeepSeek observational development pilot remains separate from RC15 engineering validation and from the frozen qualification. Its READY probe was not a task trial. One A1 runner failure has `request_status=unknown` because the CLI received the prompt before the runner failed; a later proposed retry was refused before execution. No A0/A2 task results or evaluator outcomes exist. The Windows fake-runner regression passed 12/12 cases, but that is harness evidence, not a DeepSeek trial result. Do not treat this observation as causal, qualification, or Stable evidence.

RC14 carries forward RC13's diagnostics/evidence path, reporting-independent workflow completion, and schema-complete planner validation. Independent review then found and fixed three in-scope gaps: the two adapters now use one URL/token/path redactor; Windows sandbox preflight timeout is a structured failure that preserves partial raw bytes and reserves preflight plus wrapper grace in the outer budget; and invalid reporting opt-in state is rejected before the binding is written. A0/A1/A2 thresholds and the qualification protocol are unchanged.

## RC14 evidence and release stages

| Stage | Current state | Evidence / limit |
|---|---|---|
| Unit tests | **PASS** | 101/101 tests passed on Blender-bundled CPython 3.13.13 after code, tests, and generated-runtime updates. |
| Static and packaging gates | **PASS** | Compiler check, governance lint (16 policies/8 invariants/2 managed files/0 warnings), qualification validation, freeze, repository, bundle (102 Skill lines), integrity (16 generated files), and security audit all passed. Two independent package builds matched SHA-256 `60b2770e8c3cbc96c76081bf2504b3451349fc1141f4eb39f9e33c246145dd6b`. |
| Field-tested | **Observed, diagnostic only** | Historical racing pilot compared A0/A2 in one family and one scenario; both passed 10/10 mechanical checks. Retained weak code-phase wall time was A0 14.5s and A2 72.8s; governance calls were 0 vs 7 (one A2 call failed). Token totals were not instrumented and there was no A1 arm. This single-operator n=1 observation is not a causal overhead estimate or qualification result. See [`racing-game-pilot.summary.json`](qualification/pilots/racing-game-pilot.summary.json); PR #9's unmerged raw artifacts were not imported. |
| RC14 formal dev-smoke | **FAIL at preflight** | Current RC14 attempt 1 passed registration, trial schema, artifact, and analyzer-boundary checks, then `codex doctor` reported elevated Windows sandbox provisioning incomplete/outdated. The adapter failed closed before model invocation; the task workspace changed 0 files. No model tokens or task tool calls were incurred/observed because no Agent turn started. Raw preflight stdout (15,323 bytes) remains local; its SHA-256 and the sanitized record are in [`rc14-attempt-1.summary.json`](qualification/dev-smoke/rc14-attempt-1.summary.json). This smoke is not task-efficacy evidence. |
| RC14 installed Codex Skill (historical checkpoint) | **PASS AT RC14 CHECKPOINT** | At the RC14 checkpoint, the user Skill directory had RC14; all 17 bundle files matched that candidate and the 16-file integrity manifest passed. The installed-runtime planner/lifecycle task passed, including default/opt-in status, finish, export, verified purge, removal, and sentinel preservation (record: [`rc14-installed-skill-test.summary.json`](qualification/dev-smoke/rc14-installed-skill-test.summary.json)). The earlier session's catalog snapshot returned RC12; that historical discovery result is not the current-task RC15 check above. |
| Hosted review | **DRAFT PR OPEN** | Current RC15 candidate is [PR #14](https://github.com/ouroboros965018276-collab/universal-project-governance/pull/14). PR #13 is the superseded RC14 review. This record does not imply merge or release. |
| Locked qualification | **NOT RUN** | Reviewed external isolation and three independently usable Agent families are not yet established. |
| Empirical qualification | **NOT ACHIEVED** | No locked result round admitted; no causal efficacy, cross-family handoff, efficiency, or subgroup claim. |
| Stable | **NOT ACHIEVED** | Existing release thresholds remain in force and unmet. |

The protocol still requires paired A0 baseline, A1 attention-control, and A2 UPG evidence over task/governance outcomes, safety, cleanup, handoff, trigger behavior, and token/time/tool costs. Serious safety failures are non-compensatory; zero observed events retain a non-zero upper risk bound. Any new MiMo/DeepSeek/Codex cross-host pilot must record the actually observed model, host, permissions, tools, and missing cost fields. Handoff trials must prevent chat/private-thought leakage, retain a fixed holdout separate from development tasks, and treat a small diagnostic batch as non-qualifying. `qualification/lib/contracts.py` remains the canonical authority for frozen identity and analysis settings.

RC12 and RC13 historical evidence remain unchanged. RC12 acceptance remains 1 FAIL + 4 BLOCKED; prospective attempts 13/14 keep their unknown causes. RC13 smoke attempt 3 was a fail-closed Windows sandbox diagnostic; attempt 2's invocation and usage remain unknown, not zero. These records do not describe RC14 execution. Raw logs stay local and published summaries contain bounded sanitized metadata.

## RC14 change provenance and verification

Parent source revision: `4910e7fc76b7a446775d4313823dba0acc9ca0a0`, Git commit time `2026-10-05T11:35:28+08:00`. The prior RC13 freeze was `sha256:31f754a18bd07cd07339eb148e726ac6df817032f71dc65506f63461e75234a7`; RC14 freeze is `sha256:e6e2bce7d6127655f49e88fd8d9e90e3ef2c0535c03fef1df5e2d6446d258b45`. This review-fix workflow was first recorded at `2026-10-08T16:10:59.877343Z` in the candidate checkout's `.governance/upg.json`; earlier RC14 edit-start time is unknown. RC14's only real-Agent attempt was registered under the RC14 freeze and failed closed at the sandbox gate; it did not invoke a model.

The installed runtime remains a generated bundle from `governance-src/`. At the RC14 checkpoint, its on-disk installation and temporary lifecycle test passed while that session's catalog snapshot still showed RC12. The current-task RC15 installation check is recorded above. The Codex adapter is development-only with process-level workspace isolation and no operator attestation. The existing Codex doctor warning shows Windows sandbox provisioning incomplete, so do not treat a blocked smoke as an Agent efficacy result. The three prior RC13 attempt summaries remain historical. Exact commit, hosted CI, and release decisions update only when observed.

## Structure and bounded universal scope

Maintained-project/model/host-agnostic Skill; canonical semantics in `governance-src/`, deterministic compiler, generated `universal-project-governance/`, repository-only qualification. Bounds remain 16 policies, 8 Hot Path invariants, 102 Skill lines and at most two persistent owned project files. Unknown optional profiles fall back to universal rules. Existing Git/project truth supplies history; no parallel chronology database or additional profiles. The prior RC14 installation checkpoint and current-task RC15 disk/catalog observations are recorded separately above.

## RC9 contract-integration checkpoint (historical)

Observation: 2026-10-03T14:03:08.697711Z, local UTC checkpoint; original edit-start unknown. Parent revision: `683b1ff0f85b36e9db38557d893051dcbc29ba50`, Git time `2026-10-03T13:46:36Z`. Before: equivalent freeze checks were repeated across consumers and external configuration rejection lived only in the analyzer. After: a single responsible contract layer supplies the candidate to all three consumers; admission validates settings before considering empty evidence. Reason/source: owner instruction to integrate into the whole structure, final audit evidence, and the existing STRUCTURAL_INTEGRATION invariant. Superseded duplicate checks and analyzer-only rejection are removed; no domain expansion or threshold changes.

Local engineering evidence: 69/69 tests, including changed settings, empty-evidence drift rejection, and refusal before registration/locked execution. The current freeze is `sha256:054864a6c2675610f23dfed718416109346dfd4f3bb47bf38c6323b3de321b86`. Previous main Run #200 passed all nine jobs, including private default-branch installation; [Run #203](https://github.com/ouroboros965018276-collab/universal-project-governance/actions/runs/37128361654) validates frozen revision `e3916a8aab43e23054127b65844916ce6aa50c8b` with nine successful jobs. Its Git commit time is `2026-10-03T14:04:22Z`; current acceptance observation is 2026-10-03T14:08:34.960184Z. [Run #206](https://github.com/ouroboros965018276-collab/universal-project-governance/actions/runs/37128763928) verified promoted main `3f1f8379d0392fe19cff9ecef54130b187f0aad9`: 9/9 jobs PASS, private default-branch install PASS. Git records this change's eventual source commit and commit time; neither is guessed here.

## Previous changes and causal continuity

| Full source revision | Git time (UTC) | Function, reason and evidence |
|---|---|---|
| `b9bde7c20574c9e93cc983134c6c306ee29fba1e` | See Git commit | Close custom thresholds/protocol identity loophole found in final review; Run #197 nine jobs PASS. Its qualification fingerprint is superseded by the current contract integration. |
| `7547d96008a3081c5156210ab9f1f04c22c2bbce` | See Git commit | Record observed configuration acceptance; Run #199 nine jobs PASS. Merged as parent main `683b1ff0f85b36e9db38557d893051dcbc29ba50`; Run #200 nine jobs PASS. |
| `cf81a667722ce8edcfaec4c1dd07666b32e6a4e8` | 2026-10-03T13:21:13Z | Run #189 exposed Windows cp1252 Chinese JSON stdout failures. ASCII JSON transport preserves decoded Unicode; live freeze enforcement and regression added. Run #191 nine jobs PASS. |
| `31896578b73ae0207d2a1bf8d35ad8ff5608b4a7` | 2026-10-03T13:11:15Z | RC8 audit remediation at source/compiler/state/qualification layers; Run #189 seven jobs passed, two Windows jobs failed, repaired above. |
| `2127d022d3bb0db636324b0355ef307993486371` | 2026-10-03T11:07:15Z | Audited RC8 baseline; Windows 44/47 established repair rationale. Earlier squash implementation detail is not invented. |

RC8 documents stated checkpoints `2026-10-03T19:06:41+08:00` and `2026-10-03T18:54:06+08:00`; these are stated times, not independently observed code/commit times. RC9 active progress checkpoint was observed at `2026-10-03T12:51:59.340996Z`; original work-start is unknown. The readiness audit retains prior acceptance observations. Git preserves actual source commits and parents. Use causal references and monotonic ledger sequence for order; recording time is observation time.

## Bounded runtime checks and factual limits

Synchronization observation: 2026-10-03T17:44:40.802992Z (UTC), parent main `bc0890f41297f6ebc20185c383cdba663ac46b43`; this is an observation, not an invented test/work start. Prior current-truth closeout main passed Run #210: nine jobs including private default-branch installation. This synchronization changes current-state/audit metadata only; the frozen semantics and installed Skill bytes remain unchanged.

The owner-authorized five micro-projects were delivered, locally adjusted, recovered in a fresh task context and actually checked. Current CLI, offline browser, SVG/PNG, pendulum and astronomical-window functions pass. CLI recovery found malformed JSON returned exit1 rather than the documented exit2; the existing argument boundary now rejects it and non-finite timeout values correctly. The external experiment completion helper now requires actual source/runtime/command-log receipts before commit, compares committed bytes before reporting, refuses overwritten completion input, and rejected 35 explicitly marked invalid receipt fixtures. These are project/experiment-tool corrections, not RC9 product semantic expansion.

The owner-authorized top-down racing diagnostic pilot produced two as-similar-as-possible offline games under A0 no-skill and A2 full-UPG arms. Both passed the same mechanical acceptance suite 10/10. The unmerged RC9 PR #9 record retained code-phase wall clock A0 14.5s/A2 72.8s and governance calls A0 0/A2 7 (one failed); token totals were not instrumented and no A1 arm ran. These weak single-operator n=1 aggregates cannot support a causal overhead estimate. Only the desensitized aggregate summary is recorded in `qualification/pilots/racing-game-pilot.summary.json`; no raw PR #9 artifact or private project source was imported. The pilot remains same-family, single-scenario, non-locked field evidence, not formal dev-smoke or causal qualification. The A2 field report feedback is absorbed by RC10's schema and planner-output changes.

A later, separate development-only reciprocal handoff exercise used two bounded micro-projects. Both directions completed across fresh contexts: one continuation was independently rerun by the originating actor; another initial implementation was resumed at its reserved follow-up, then reconstructed and read-only checked by the receiving actor. The scoped checks passed. A sanitized, date-ordered audit is in [the reciprocal handoff audit](audits/rc9-reciprocal-handoff.audit.md); underlying project files, samples, local paths, actor/provider details, and raw evidence remain outside this repository. This is a bounded workflow exercise, not formal dev-smoke, locked qualification, model-family independence evidence, or a Stable gate.

Strict original-workflow acceptance is NOT PASS. The pendulum adjustment originally described an overflow-input assertion as division by zero; the correction retains the original inaccurate record, so historical governance is FAIL. The other four workflows lack complete historical test-time source-tree evidence (astronomy also lacks a retained historical live-source response), so those historical checks remain BLOCKED. New current-version checks do not retroactively certify missing evidence. The readiness audit records full micro-project revisions and SHA-256 identities of operator-local retained evidence; the evidence itself and experiment source are not uploaded into this repository. Current functional PASS is not full five-workflow governance PASS or formal statistical qualification.

Remote RC9 completed-branch cleanup is verified COMPLETE as observed 2026-10-03T18:04:56.030372Z (UTC). After authenticated built-in-browser access became available, each of the four branches was confirmed merged with zero commits ahead, deleted through its merged PR, and absent from the authenticated API branch list. The earlier branches-page request failed with Failed to fetch; that failed attempt remains retained as history. Local merged refs were also removed; commits are preserved in main. Main `e9c4d52ab0008b1a2e682b6d3dd6bccd428645fd` passed Run #213, 9/9 including private default-branch installation. This hygiene observation does not rewrite historical test outcomes. The existing readiness audit is the canonical machine-readable outcome and pending-item record; no parallel history database is introduced.

## Handoff and next phase

The development-only official API acceptance utility first failed locally before provider invocation: the initial ledger (SHA-256 `8913e60f07653cf2a6fb4aaabdfc074855fce19792ce80ce0a9d219a1fc7c4cd`) records zero requests and no usage. `[System.IO.File]::Replace($temp,$Path,$null)` raised `ArgumentException` at `deepseek-ledger-inflight`; same-volume `File.Move(..., overwrite)` now writes successive checkpoints and sanitized worker failures. A later user-approved first acceptance run is in a separate sanitized ledger (SHA-256 `1283cb43a85555ea941df28da7af51e04134c81683d7b4a8150bc8e1fc16be97`): DeepSeek `deepseek-flash`, 1 request, controlled function validation, usage 333/41, estimated CNY 0.000994, reserve CNY 2.002048; MiMo `mimo-v2.6-flash`, 1 request, controlled function validation, usage 148/26, estimated CNY 0.000200, reserve CNY 1.000512. Exact HTTP codes are not logged; success passed the utility's HTTP success check. The application policy is one request per provider with no retry/fallback. This covers one controlled function return each, not a complete multi-turn exchange, invoice settlement, or formal qualification; no keys are persisted. The scripts remain repository-only and do not alter the generated Skill or qualification thresholds. Validation: repository check passed; Python unit tests 105/105, API mock/static assertions 64/64, UI fake-path assertions 13/13, and four PowerShell files parsed successfully.

Engineering acceptance completed on main `3f1f8379d0392fe19cff9ecef54130b187f0aad9` with Run #206, nine successful jobs including private default-branch installation. Exactly one completion report and verified export were recorded locally; full external stage acceptance is retained. Current-truth reconciliation observed 2026-10-03T14:49:48.477273Z; reason: replace pre-merge pending language with observed post-merge facts. Frozen semantics are unchanged. The owner now authorizes five bounded real micro-project runtime checks in `the dedicated local experiment workspace`; these are separate from formal locked statistical qualification. Next phase separately verifies real adapters, enforced isolation, independent model families, budgets and externally sealed preregistration/order before executing any round. Real results enter immutable `results/qN/` only after execution; no synthetic engineering fixture is efficacy evidence. Existing software/data tasks do not prove efficacy across every domain; generated handoff plans are same-family unless separately registered/reviewed.

After interruption, reconstruct from Git/current project truth, validation and active binding; unknown intent stays unknown. Export and verify evidence before epoch rotation. Inspect transient lock/temp residue before recovery. Preserve project-owned contracts and specialized workflows.
