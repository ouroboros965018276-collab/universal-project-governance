# Publishing and Test-Freeze Gates

Current candidate: **3.0.0-rc.18 — Grader Validity and Measured Runtime Compression**

RC18 repairs demonstrated task-grader false positives, compacts canonical runtime instructions, accepts UTF-8 BOM JSON in runtime helpers, and binds native development measurements to their exact execution inputs and budgets. Completed paired measurements, the audited nine-arm development round and release work are recorded in [PROJECT_STATE.md](PROJECT_STATE.md); RC17's audit retains its original scope. Final local regression passes 299/299 tests in 98.700 seconds, including post-measurement bounded checkpoint-I/O retry hardening, and all eight local release gates pass. Hosted CI passes 11/11 at measured freeze `8d1cb51945c5d98bf3db7c2e72557d7e50274275`; final PR/main CI is recorded separately. Publish only after this candidate's own compile, regression, integrity, isolated lifecycle, deterministic-package and privacy checks pass. Qualification thresholds and historical outcomes are unchanged. Empirical admission remains BLOCKED and formal qualification is UNASSESSED: locked qualification is NOT RUN; empirical qualification and Stable are NOT ACHIEVED. No learned candidate is promoted. Pre-merge installation snapshot: the user-level Skill is RC17, and RC18 is prepared but not installed at that snapshot; later deployment needs its own observed acceptance record.

The [eight-pair RC17/candidate artifact measurement](qualification/pilots/rc18-native/paired.summary.json) contains 16 fresh calls with all task checks passing: input tokens decrease 3.85175% and total tokens 3.84511%. Full evaluator callback time, including isolated compilation, planning and grading, has a +23.6975% point estimate; the time-ratio 95% interval [0.95923, 1.51345] includes 1, so timing improvement is unestablished. Compiled `SKILL.md` shrinks from 11144 to 7940 UTF-8 bytes (28.75%); this is a separate byte measurement. The [v1 matrix](qualification/pilots/rc18-native/round-v1.summary.json) stopped after a safely rejected invalid learner edit incorrectly aborted the full arm; five arms did not run. Its checkpoints and costs remain intact. The [freshly preregistered v2 nine-arm round](evolution/protocol/rc18-native-development-v2.json) completed 9/9 arms and passed experiment-record audit: 188 actual CLI turns (158 task, 30 learner), 2684192 tokens, 158/158 raw task results passing mechanical regrading and 0 final-task dispatches. Two temporary Windows checkpoint replacement denials were reconciled before same-freeze recovery; additional calls are counted, while the occupying process and specific cause remain unknown. Trials total 227 turns / 3238130 tokens, including paired calls within v1; the separate capability probe brings totals to 228 turns / 3253051 tokens. No final-task feedback is reused and no causal algorithm benefit is established. Requested `gpt-6-luna` identity is not yet provider-confirmed; completed-turn token reports do not establish provider-internal retry coverage. JSON artifact repair does not establish real tool execution or cross-Agent handoff. None of these observations bypasses the independent final-evidence or formal locked gates.

## Engineering gate before real-Agent testing

All must pass:

```bash
python compiler/compile_governance.py --check
python tools/governance_lint.py .
python tools/validate_qualification.py .
python tools/qualification_freeze.py . --check
python tools/validate_repository.py .
python tools/validate_skill_bundle.py universal-project-governance
python universal-project-governance/scripts/validate_integrity.py universal-project-governance
python tools/security_audit.py .
python -m unittest discover -s tests -v
```

CI must also pass Linux Python 3.8/3.11/3.13, offline-evolution Python 3.10/3.13, Windows Python 3.11/3.13, upstream Agent Skills validation, local lifecycle install/remove, clean Codex-target installation, deterministic packaging, and private default-branch installation after promotion.

## Real-Agent locked gate

One immutable result round under the current qualification fingerprint must satisfy every non-compensatory gate:

Evidence admission comes first: registered round, current frozen identity, schema-valid isolated executions, matched model/adapter/host conditions and retained artifact bytes. Rejected inputs never reach release inference. Analyzer exits 1 for FAIL and 2 for MORE_DATA; neither exit promotes Stable.

1. complete locked scenario/Agent/arm coverage;
2. project deployment integrity and completion reports;
3. evaluator mutation sensitivity;
4. attention-control validity;
5. class-specific critical safety;
6. scope-overreach control with independent `local_guard` and `structural_guard` exposure/confidence bounds;
7. core-task non-inferiority;
8. governance uplift;
9. handoff recovery and degradation reduction;
10. trigger precision/recall;
11. token/time/tool/task-artifact/managed-file efficiency;
12. subgroup generalization under explicit CI semantics.

## Formal inference

Primary CIs use preregistered hierarchical bootstrap over Agent family → scenario → pair/repetition.

Subgroup CI evidence is reported directly. Generalization PASS means the preregistered severe-reversal criterion is established; it does not silently imply significant benefit in every subgroup.

## Field-test evidence

Personal and friend gray testing may export `upg-field-test-reports.json`. These reports are diagnostic field evidence, not substitutes for locked qualification.

Before Stable, the report capability receives an explicit retain/remove decision. The disabled path is already executable: fresh binding creates no ledger and report/export operations are unavailable. Existing non-empty ledgers must be exported and purged before retirement; `remove` refuses to proceed while history remains and never silently discards it.

## Freeze rule

After `qualification/FREEZE.json` is regenerated for the current candidate, no frozen surface changes during a result round. Any such change invalidates the round and requires a new fingerprint.
