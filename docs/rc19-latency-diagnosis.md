# RC18 elapsed-time investigation

RC18's eight prespecified artifact pairs remain the reported result: total
completed-turn tokens fell 3.8451%, while full callback elapsed time rose
23.6975%. The latency interval included both improvement and regression. The
following investigation explains measurement components; it does not replace
that result or turn the old final tasks into a new independent holdout.

## Observed decomposition

| Component | Treatment minus control | Share of full increase |
| --- | ---: | ---: |
| Full callback | 16.820870 s | 100% |
| CLI subprocess | 10.632996 s | 63.21% |
| Remaining callback time | 6.187873 s | 36.79% |

One pair, `final-dependency-0`, contributed 16.105011 seconds, or 95.74% of
the full increase. Its CLI elapsed times were 9.411548 seconds (control) and
21.164483 seconds (treatment); the residual times were 1.528238 and 5.880314
seconds. Both responses reported 64 output tokens and zero cached input tokens.
The historical events do not explain this tail latency. In particular, CLI
wall time is not a measurement of provider-only inference or server time.

The other seven pairs had a combined full-callback difference of +0.715858
seconds and a lower combined treatment CLI time. This is a sensitivity check,
not an alternative primary estimate or a reason to exclude the slower pair.

## Reproduced local overhead

A no-model experiment used four alternating repetitions per condition, the
original frozen source/compiler/runtime, a substituted local completion and a
subprocess guard permitting only the exact compiler/planner Python commands.
It retained actual compilation, planning, binary verification and grading.

| Median local component | Historical control | Candidate treatment |
| --- | ---: | ---: |
| Callback | 1.463656 s | 1.796483 s |
| Binary reads and SHA-256 | about 0.989 s | about 1.000 s |
| Compiler | 0 s | 0.454736 s |
| Planner | 0.298191 s | 0.227933 s |

The 336,100,304-byte CLI executable was read and hashed three times per task
callback: about 1.008 GB of local reads. The control materialized its exact
historical runtime, while the treatment launched the compiler on every callback.
This is a real preparation asymmetry. Neither local medians nor this asymmetry
identify the cause of the exceptional historical residual.

## RC19 changes and acceptance

RC19 retains a full executable hash before every dispatch, reuses clients only
for identical explicit configurations, and caches deterministic preparation
under the exact source, compiler, license, runtime, context and Python identity.
Every cache hit verifies all stored bytes. No model observation is manufactured
or reused as a fresh independent sample. Cold preparation, warm preparation,
capability verification, CLI and grading costs are recorded separately.

With the same frozen inputs and no model calls, three warm repetitions per
condition had median callbacks of 0.367921 seconds (control) and 0.346563 seconds
(treatment), versus the original 1.463656 and 1.796483 seconds. Each warm dispatch
still read and hashed the entire executable once; it launched no compiler or
planner. These local medians fell about 74.9% and 80.7%, respectively.
One cold sample per condition remained 1.131195 and 1.636959 seconds, plus a
separately measured one-time client anchor of 0.518906 seconds. The treatment's
cold compilation took 0.701071 seconds. Cold and warm measurements are separate,
small local samples and establish no end-to-end model speedup.
They used warm operating-system caches, different small repetition counts and
possibly concurrent host load. The percentages are descriptive microbenchmark
changes, without a statistical or general latency claim. Cache byte digests
check consistency within the trusted Python process; they are not an
authorization or isolation boundary.

The planner's JSON whitespace is compacted without changing any plan value.
The canonical Skill adds guidance for bounded context, independent-operation
batching and verified reuse, while retaining its governance obligations.
Text size, local tests and preparation speed are engineering measurements;
real-task token and elapsed benefit requires a separate frozen comparison.

The intended new comparison uses new tasks, two catalog-observed requested
models and bounded repository tools. Its first development transport failed:
[all eight calls used zero tools](rc19-tools-development-v1.md), with their
known costs retained. Useful real-tool evidence requires a corrected transport.
Positive structural validators and an
independent tool journal check the result. This profile executes no submitted
application code and establishes neither container isolation nor multiple
provider families. Formal qualification remains unassessed.
