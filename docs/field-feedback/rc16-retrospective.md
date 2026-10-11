# RC16 field-feedback disposition

This is a sanitized engineering input to the RC16 candidate, not an efficacy evaluation or a Stable release claim. The machine-readable disposition is [`rc16-feedback.json`](rc16-feedback.json). It contains bounded issues, not copied project history. No private project was changed, no historical record was backfilled, and these sources do not prove historical Skill activation.

## Evidence and limits

**Case-A** is the incremental observation already published in [feedback #15](https://github.com/ouroboros965018276-collab/universal-project-governance/issues/15#issuecomment-6105963130). This update remains one project case. Its author inspected installation, readable commits, and existing governance records, without rerunning project tests or invoking the lifecycle helper. A separate [public synthetic reproduction](https://github.com/ouroboros965018276-collab/universal-project-governance/issues/15#issuecomment-6096568028) on public candidate `42a72ff` established a helper defect in both reporting modes: completion rejected changed result metadata, but accepted unchanged start metadata and cleared the active workflow. Synthetic revisions establish tool behavior, not project outcomes. The observed project completion has a similar shape; editable records do not prove it took this helper path.

**Case-B** is an owner-supplied retrospective attachment. This investigation read that summary, not its private project, original logs, repository, or governance files. Every Case-B count and behavioral assessment below is an unverified self-report. The attachment's recommendations are evidence to evaluate, not instructions to execute against that project.

| Source | Retained aggregate observations | Interpretation limit |
|---|---|---|
| Case-A installation/change | Catalog discovery; 16/16 manifest entries matched; 2 added commits, 24 files, +480/-229 lines; governance sequence 7 to 8 | Discovery and local manifest consistency do not prove per-round activation, independent provenance, or causation. Commits and sequences are not independent task samples. |
| Case-A accepted round | Recorded 76/76 affected headless tests; 2 additional package checks overlap | Not 78 independent tests; no GUI automation or independent rerun. |
| Case-A continuing work | 28 validation records; earlier broad round 552/623 passed, 71 failed; newer focused round 144/145 passed, 1 failed | Different, potentially overlapping scopes. Neither sum the counts nor infer that the whole project has only one remaining failure. An assertion adjustment awaits final retest. |
| Case-A inaccessible worktree | 36 tracked-modification markers; 19 numbered project constraints | Markers do not establish diff contents or complete scope; rule counts do not establish governance cost. Access errors leave uncertainty. |
| Case-B activity | Reported 60 conversation rounds, 134 commits, 135 changed files, +31903/-494 lines; paired feature/pin commits | Conversation turns and paired commits do not constitute 60 or 134 independent completed workflows. |
| Case-B validation/governance | Reported 65 existing evidence paths, test count 130 to 527, 6 corrections, 2 passing gates; ledger contains 2 earlier reports and no report for the described upgrade; active result remains unknown | Path existence does not establish content validity. Growing test counts do not prove no regression or net efficacy. Missing call receipts do not prove the helper was never called. |

Project names, private paths and revisions, workflow identifiers, identities, source snippets, raw logs, and source-event timestamps are withheld. The public candidate identity and public feedback links are retained solely for reproducibility. New artifact `updated_at` is this disposition's recording time, not a reconstructed source-event time.

## Change disposition

| Feedback | RC16 engineering response | Evidence still required |
|---|---|---|
| FB16-01: results cannot evolve | Separate immutable start identity/checkpoint from completion result; permit factual result updates, retain start facts, retry idempotence, and conflict rejection | Implemented; 18/18 lifecycle regressions and 136/136 full suite pass. Field cause remains unknown |
| FB16-02: stale handoff/test claims | Let execution and handoff reference one validation record with round, scope, denominator, result, tested state, subsequent changes, and pending retest | Implemented; 13/13 continuity regressions and 136/136 full suite pass. Real field recovery remains unqualified |
| FB16-03: stage work absent from lifecycle | Use the existing begin/finish lifecycle for deliberately bounded completed tasks; keep partial/blocked work active | Prospective task completion, not one forced finish for an unfinished umbrella workflow |
| FB16-04: installation mistaken for activation | Preserve unknown historical activation; accept an optional independent host receipt only where supported | Actual host capability and receipt; a Skill-authored declaration is not independent evidence |
| FB16-05: cost/benefit unmeasured | Reuse the existing qualification protocol for paired outcome and cost measurement | Real independent trials with comparable token, time, and tool cost |
| FB16-06: broad release/blocker claims | Keep RC16 a candidate; retain authorization and remaining engineering work as separate blockers | Qualification and actual affected acceptance evidence |
| FB16-07: chronology/signals overreach | Preserve unknown times; use observed source references where available; distinguish task signals from validation results | Explicit mappings and source-specific time meaning, without inventing old outcomes |

FB16-01 and FB16-02 are resolved only for the implemented engineering contracts; the other five items remain open. Independent cross-review found two retry-edge defects, both repaired before the final 136/136 suite. Even an engineering fix does not close field-efficacy questions. External referenced sources must be retained separately: the current export does not snapshot them.

Do not apply the retrospective's proposed whole-workflow completion: it also describes unfinished integration and acceptance work. A final commit alone cannot prove the stated scope complete or validated. Authorization and budget gaps are not the sole blocker when implementation and regression work also remain. A Git committer date is a commit timestamp, not automatically a task's occurrence time. Do not rewrite historical unknowns, blindly map contextual signals to PASS/FAIL, automatically finish on every pin commit, or promote a candidate to Stable on these reports.

## Prospective evaluation, not executed

Reuse [`qualification-v3.json`](../../qualification/protocol/qualification-v3.json) and its existing thresholds. Start with diagnostic fresh-workspace tasks comparing A0 (no Skill), A1 (attention control), and A2 (UPG), with matched scenario, Agent/model/scaffold, adapter/host, tool and budget conditions. Register outcomes before execution; retain failures, unknown usage, denominators, overlap, and actual costs. Measure task success, severe failures, cleanup, scope overreach, governance correctness, injected/retrieved tokens, wall time, tool calls, and maintenance effort. Do not treat commits, tests, or rule counts as benefit measures.

Include two-Agent handoff and three-Agent continuation chains, both explicit handoff and abrupt interruption. Receivers reconstruct from current project truth and shared validation references without private conversation memory. Record source and receiver identities, recovery success, lost risks, stale-round selection, and added cost. These are prospective diagnostics; they do not replace locked handoff coverage or imply cross-Agent generalization.

Stable evaluation still requires the protocol's locked matrix, reviewed strong isolation, at least 3 independent Agent families and 2 project profiles, prescribed repetitions, blinded grading, and immutable evidence. No paired trial, formal cross-Agent handoff qualification, cost-effect estimate, or Stable qualification was executed for this feedback disposition.

## Limited receiving-agent diagnostic executed

One independent receiving subagent used the candidate Skill and a fresh isolated synthetic arithmetic project. It received the written task and project artifacts without the intended answer or parent-task conclusions. It recovered the written contract, reran the existing suite (2/3 before, 3/3 after the correction), reconciled the canonical validation reference, preserved the original workflow start and completed the reporting-off lifecycle with healthy state. These counts apply only to the three existing synthetic tests. The raw isolated artifacts remain local. This is a same-family development diagnostic with no A0/A1 match, measured cost comparison, independent-family coverage or formal qualification claim.
