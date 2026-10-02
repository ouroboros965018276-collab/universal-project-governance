# Governance Feedback Loop

Load this reference in evaluation mode or when the execution reveals something that should improve
future governance behavior.

## Purpose

The feedback loop exists to answer:

- Did the Skill change agent behavior in the intended direction?
- Did it miss an important failure mode?
- Did it trigger when it should not?
- Did it impose unnecessary ceremony/token cost?
- Could the next agent continue without hidden context?
- Did a user have to correct the agent because the governance contract was unclear or insufficient?

## Capture useful signals, not routine noise

Create feedback only for evidence-bearing events such as:

- user correction;
- unsafe or incorrect attempted cleanup;
- validation/rollback failure attributable to governance behavior;
- a rule ambiguity that blocked or misdirected work;
- repeated technical-debt residue;
- duplicate source-of-truth creation;
- handoff failure or missing context;
- false positive activation or excessive report generation;
- false negative activation;
- a recurring manual workaround.

Routine successful tasks need no feedback entry.

## Feedback record

A useful feedback item contains:

- observable event;
- expected behavior;
- actual behavior;
- evidence/reference;
- impact;
- likely rule/tool gap;
- proposed improvement, if any;
- status: open / accepted / rejected / resolved.

Do not include hidden chain-of-thought. Record only observable facts, decisions, and evidence.

## Skill changes require separation

Feedback may recommend changing the Skill, but **must not modify protected Skill files during the
ordinary project task that produced the feedback**.

Skill evolution is a separate authorized governance-upgrade task governed by `INTEGRITY.md` and
[version policy](version-policy.md).

## Retention

- open findings remain visible;
- resolved findings should be folded into the relevant Skill change, changelog, eval, or decision;
- redundant resolved raw feedback may then be removed or summarized;
- release-critical evidence remains with the release audit when required.

This prevents the feedback system itself from becoming an ever-growing backlog of obsolete prose.

## External review

In evaluation/testing, use `scripts/export_evidence_bundle.py` to produce a compact review bundle
containing governance state, handoff, open feedback, and recent execution/audit evidence. Source code
is excluded by default.
