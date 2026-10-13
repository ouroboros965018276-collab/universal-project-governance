# 通用项目治理 | Universal Project Governance

## 当前版本与开发进度 | Version status

当前候选版本 / Current release candidate: **3.0.0-rc.19 — Project Fact Recovery and Measured Execution Cost**。已整合按需项目事实恢复与原生离线反思学习，并完成默认分支合并与本轮本地主机安装验收。独立 token／耗时净收益仍未证实。

发布状态 / Release: **候选，非 Stable**。RC19 已通过 [PR #20](https://github.com/ouroboros965018276-collab/universal-project-governance/pull/20) 合并到默认分支，[PR #21](https://github.com/ouroboros965018276-collab/universal-project-governance/pull/21) 记录了本轮本地主机的[安装验收](audits/rc19-installation.audit.json)。RC19 的[耗时诊断](docs/rc19-latency-diagnosis.md)区分单次长尾与可复现的本地开销；发布与安装通过不代表真实模型端到端净收益已成立。版本以 [VERSION.md](universal-project-governance/VERSION.md) 为准，当前状态见 [PROJECT_STATE.md](PROJECT_STATE.md)。

### RC18 历史实测（保留原始范围）

[八对测量](qualification/pilots/rc18-native/paired.summary.json)包含 16 次全新调用，全部任务检查通过：输入 token 减少 **3.85175%**，总 token 减少 **3.84511%**。包含隔离编译、规划和评分的完整回调耗时点估计增加 **23.6975%**，时间比的 95% 区间包含 1，未证实耗时改善。编译后 `SKILL.md` 从 11144 减至 7940 个 UTF-8 字节（**28.75%**），字节缩减与 token 缩减分别记录。[首轮记录](qualification/pilots/rc18-native/round-v1.summary.json)保留无效学习编辑被安全拒绝、控制器却错误中止整组的失败；[v2 协议](evolution/protocol/rc18-native-development-v2.json)不复用最终任务反馈。实证准入仍为 **BLOCKED**，正式资格为 **UNASSESSED**，未提升任何学习候选。

v2 记录 188 次实际 CLI turn（158 次任务、30 次学习），共 2684192 tokens；158/158 原始任务结果机械重评分通过，最终任务分派为 0。两次 Windows 检查点替换临时拒绝均在核清已付费调用后按同一冻结协议和引擎恢复，额外调用全部计入预算，具体占用进程或原因未确认。v1 与 v2 合计 227 次调用、3238130 tokens；另有能力探针 1 次、14921 tokens，含探针总计 228 次、3253051 tokens。发布阶段另加入有界检查点 I/O 重试，最终本地回归 **299/299 通过（98.700 秒）**、发布门禁 **8/8 通过**，未追溯更改实测引擎。实测冻结版本 `8d1cb51945c5d98bf3db7c2e72557d7e50274275` 的托管 CI 为 **11/11 通过**；最终 PR/main CI 另行记录。九组完成不建立算法因果收益，详见[实测报告](qualification/pilots/rc18-native/README.md)。

离线引擎使用 Python 3.10+；日常 Skill 无新增模型调用，辅助脚本继续支持 Python 3.8+。见[离线优化说明](docs/offline-evolution.md)。本轮本地主机已验收的 Skill 为 RC19，见[安装审计](audits/rc19-installation.audit.json)；远端合并不会自动更新其他主机或本地副本。

上述 RC18 文件任务只评估模型返回的 JSON/源码内容，不执行生成代码。RC19 已有实际文件/Git 工具开发记录，但净收益门禁未通过。请求模型的提供方内部身份和内部尝试费用覆盖仍未知；正式资格门禁保持不变。

状态日期：**2026-10-13 Asia/Shanghai**。

Universal Project Governance is a model-agnostic, host-agnostic Agent Skill for maintained-project governance across software, data, infrastructure, research, content, product/specification, operations, design systems, automation, ML/AI, documentation, and mixed projects.

RC16 addresses two field-feedback gaps: completion could not replace planned outcomes with observed results, and a handoff could repeat stale validation prose. The lifecycle now separates start facts from evolving outcomes. Optional validation references resolve one named, scoped run from the existing project truth and reject stale digests. Original unknowns remain honest; stage checkpoints do not complete unfinished work. See the [sanitized feedback and evidence limits](docs/field-feedback/rc16-retrospective.md).

The prior frozen RC13 smoke passed registration, schema, artifact, and analyzer-boundary checks but failed closed before model invocation because Windows sandbox provisioning was incomplete; its sanitized record is [`qualification/dev-smoke/rc13-attempt-3.summary.json`](qualification/dev-smoke/rc13-attempt-3.summary.json). RC14 attempt 1 independently reproduced the same preflight blocker after registration/schema/artifact checks against its then-current RC14 freeze; the adapter made no Agent call, and its sanitized summary is [`qualification/dev-smoke/rc14-attempt-1.summary.json`](qualification/dev-smoke/rc14-attempt-1.summary.json). The interrupted RC13 attempt has registration only, so invocation and usage remain unknown, not zero ([record](qualification/dev-smoke/rc13-attempt-2.summary.json)). Historical RC12 outcomes remain unchanged: 1 FAIL + 4 BLOCKED, and prospective attempts 13/14 keep their unknown causes. Locked qualification remains NOT RUN; empirical qualification and Stable remain NOT ACHIEVED because reviewed external isolation and three usable independent Agent families are not established.

## What changes when installed

RC19 adds optional [project fact recovery](docs/project-fact-recovery.md) for
interrupted, stale or contradictory project state. It checks explicit file
scopes and evidence references, separates static declarations from actual
validation, and carries justified decision changes through the existing handoff.
Ordinary local changes retain the lightweight path. RC19 is merged and locally
installed under the owner's engineering-release authorization; independent
measured token/time benefit remains unverified. See the
[installation audit](audits/rc19-installation.audit.json).

Without UPG, an Agent can still complete a task, but cleanup, current-truth updates, validation evidence, scope discipline and handoff recovery depend on the Agent remembering to do them. With UPG active on a maintained-project change, the Agent first observes available capabilities, chooses local or structural mode, keeps work inside the smallest responsible layer, removes replaced residue when safe, validates affected behavior, and records explicit unknowns instead of inventing history.

The generated plan now separates two concepts that were easy to confuse during field testing:

- `report` is the ordinary governance note level for the task.
- `field_report_obligation` says whether the temporary field-test ledger still requires exactly one completion report before claiming a modifying workflow complete.

## Five-minute quickstart

From this repository, install the Skill into a maintained project and check its binding:

```bash
python upg.py install --project /path/to/project --agent codex
python upg.py status --project /path/to/project
```

Ask the Agent for one bounded change, for example: “Rename `--old-mode` to `--mode`; update its callers, tests, and current README; remove the old flag only after confirming no references remain.” UPG should inspect the project first, change only the canonical files and their tests/docs, run the affected checks, and leave unrelated files alone. The default install does not require a persistent field-test report.

For a gray test or qualification run that must retain one bounded report per completed modifying workflow, opt in explicitly:

```bash
python upg.py install --project /path/to/project --agent codex --field-test-reporting
```

The option is project-local. Existing opted-in bindings stay opted in and retain their report history; ordinary `ensure` does not silently disable them. This is an illustrative workflow, not a claim that every domain or Agent has been empirically validated.

### Concrete difference

Without UPG, an Agent might rename the flag in the CLI but miss a stale test or README reference. With UPG, it searches the affected project neighborhood, confirms the current contract, updates all in-scope references, runs the relevant test, and reports exactly what was and was not verified. The difference is a target behavior, not an observed success-rate claim.

## Architecture

```text
governance-src/                canonical governance semantics
        ↓ compiler/
universal-project-governance/  generated installable Skill
        ↓
project binding v2             .governance/upg.json
optional field-test ledger     .governance/field-reports.json
        ↓
human / coding / workspace / browser / tool-using Agent work
        ↓
qualification/                 repository-only causal qualification
```

Qualification code never ships as Agent runtime. The field-test ledger is created only for projects that opt in.

## Universal continuity

A planned unfinished transition should use one current handoff. RC9 does not assume that a previous actor had time to create one.

After quota exhaustion, crash, session loss, tool failure, or another abrupt stop, the next actor reconstructs before modifying: it reads current canonical project truth, observable worktree/VCS or equivalent state, existing validation/evidence, UPG state, and unresolved artifacts. Recovered facts are separated from possibilities; unavailable prior intent stays explicitly unknown. Recovery never requires private chat memory or chain-of-thought.

## Legacy projects: effective immediately

The first modifying activation runs the idempotent project `ensure` operation.

RC9 adopts pre-UPG projects **in place**. Installation adds only UPG-owned state and does not restructure, rewrite, or demand project-wide migration of existing content. New bindings default to reporting off; pre-existing opted-in state and its ledger are preserved. Existing artifacts are evidence rather than automatically trusted design; governance applies to the current task immediately while preserving observed contracts and current canonical sources.

Owned project state remains bounded to:

- `.governance/upg.json` (always)
- `.governance/field-reports.json` (only when reporting is enabled)

An owned RC7 binding can upgrade to binding schema v2 without discarding its existing report ledger.

## Agent interoperability

RC9 does not maintain a vendor/model allowlist. Before modifying state, the Agent observes available capabilities such as filesystem, VCS, search, build/test, browser, application, or other tools, and governs with what actually exists.

The same contract therefore applies to conversational Agents, coding Agents, workspace/computer-use Agents, IDE/CLI Agents, and other tool-using systems. Missing capabilities reduce what can be verified; they never authorize fabricated validation.

## Project-type interoperability

Profiles are optional task hints, not mandatory project migrations. Current profiles cover software, data, infrastructure, ML/AI, automation, docs/knowledge, design systems, research/evidence, maintained content/editorial, product/specification, operations/runbooks, and mixed projects.

Unknown project types still receive the universal Hot Path and task/risk-triggered policies; no project is excluded merely because it lacks a named profile.

## Structural integration remains task-bounded

The planner returns `change_mode` and `scope_guard`.

- `local / local-only`: genuinely local low-risk work.
- `structural / task-bounded-responsible-layer`: non-trivial work changes the smallest responsible canonical layer and removes superseded in-scope patch paths.

Structural mode never grants permission for unrelated redesign, API/contract changes, architectural migration, or opportunistic refactoring.

## Workflow outcomes and validation references

Start non-trivial work with `project_tool.py begin PROJECT --input workflow.json`. At a real workflow boundary, call `finish PROJECT --input report.json` with the same identity and factual `change.after`, result/validation revision and sourced occurrence time. The original checkpoint is retained as `start_change`; identical completion retries remain idempotent. `unknown` remains valid. Checkpoints with `status=partial` or `blocked` retain active recovery state. An implementation pin alone does not complete the parent workflow or its externally blocked acceptance. Each workflow/status has one immutable receipt: one partial and one blocked outcome can be retained; changed same-status retries are rejected. Split deliberately bounded work at actual workflow boundaries rather than auto-finishing on every pin. Reporting-off retry verification is bounded to the retained latest/previous completion checkpoints.

Execution state may use optional `validation_runs`, with each record containing `run_id`, `scope`, `result` and `tested_revision`; `passed`, `total`, `later_changes` and `pending_retest` add explicit limits. Handoff state may instead carry a `validation_ref` with project-relative `path`, `run_id`, file `sha256` and optional JSON `pointer` to an existing structured record. This supports existing truth files without a parallel validation ledger. Validate or render references using:

```bash
python universal-project-governance/scripts/state_tool.py validate .governance/handoff.json --schema handoff --project-root .
python universal-project-governance/scripts/state_tool.py render .governance/handoff.json --schema handoff --project-root . --current-revision ACTUAL_CURRENT_STATE
```

Use an actual revision/state identifier in place of the examples. A digest mismatch or missing source requires reconciliation; it never certifies a pass. Different scopes remain separate, and later changes are pending retest. Legacy string validation remains supported. See the generated execution/handoff schemas for the precise contract. The tool verifies referenced metadata and freshness, not whether a test genuinely executed. No per-commit hook or default activation logger is installed. State export does not snapshot external referenced sources; retain those files separately when handing off or exporting evidence.

## Automated lifecycle

```bash
python upg.py install --project /path/to/project --agent codex
python upg.py status --project /path/to/project
python upg.py install --project /path/to/evaluation-project --agent codex --field-test-reporting
python upg.py export --project /path/to/project --output upg-field-test-reports.json
python upg.py remove --project /path/to/project --agent codex --yes
```

Install uses the pinned Skills CLI, validates the installed copy, and initializes/adopts the project binding. Fresh-install failure attempts owned-state and Skill rollback. Uninstall removes only UPG-owned paths and preserves unrelated project governance data.

## Gray-test report

Field-test reporting is off for new project bindings. While `field_test_reporting=true`, every completed modifying workflow must append **exactly one** bounded report. Use `--field-test-reporting` only for an explicitly opted-in field evaluation or qualification workspace. The qualification runner opts its A2 behavioral workspaces in; the deployment gate still verifies `report_count == 1`, not merely that a report exists.

Reports contain metadata/evidence summaries rather than source bodies or private chain-of-thought. The ledger is one bounded file with at most 200 entries. Report validation rejects common private-key/token patterns, Bearer/JWT-like credentials, assignment-style secrets, and credential-bearing database URLs. This is defense-in-depth rather than a claim of general DLP; participants should still review exports before sharing.

## Qualification v3 / frozen candidate identity

Formal primary confidence intervals use hierarchical bootstrap:

```text
Agent family
  → scenario
    → repetition / pair
```

The locked protocol requires at least **3 independent Agent families**. Bootstrap repetitions cannot create independent top-level information, so cross-family generalization is reported separately and remains deliberately narrower than within-family precision.

Locked evidence also binds the actual execution condition through:

- Agent family, model ID, scaffold version;
- adapter configuration SHA-256;
- adapter implementation/runtime SHA-256;
- host tool name/version;
- tool profile and budget profile;
- both source and receiving identities for cross-Agent handoff trials.

Release gates remain non-compensatory for coverage, deployment, evaluator/control validity, critical safety, structural overreach, task performance, governance uplift, handoff, trigger behavior, efficiency, and subgroup generalization.

## Evidence boundaries

Current UPG is field-tested and engineering-validated, but not empirically qualified. The TRAE diagnostic racing-game pilot built one A0 and one A2 game; both passed the same 10/10 mechanical acceptance suite. It exposed two usable improvements that were absorbed. Its retained aggregates include weak code-phase wall-clock observations (14.5s A0, 72.8s A2) and governance-call counts (0 A0, 7 A2, one failed); token totals were not instrumented. This was one family and one scenario, with no A1 arm, and was not locked. It therefore does **not** establish that UPG is more efficient, more professional, or causally better.

Profiles are routing hints and product support, not domain-by-domain effectiveness evidence. The locked task matrix currently covers software/data tasks; no causal benefit is claimed for research, content, operations, design, or other unmeasured domains.

Keep these stages separate:

- **Field-tested:** real Agents have used the Skill on actual tasks; observed defects can improve the product.
- **Formal dev-smoke:** the available host/adapter executes a registered development task end-to-end and retains reviewable evidence. This checks plumbing, not efficacy.
- **Locked qualification:** preregistered A0/A1/A2 trials use frozen identities, external isolation attestations, at least three independent Agent families, and immutable artifacts.
- **Empirical qualification:** locked evidence is admitted and all non-compensatory gates pass.
- **Stable:** release promotion follows only after the qualification contract is met.

**Qualification evidence boundary:** The RC9 field pilot retained weak single-family timing and governance-call aggregates for A0/A2; token totals were not instrumented, there was no A1 arm, and the observations cannot support a causal overhead estimate. RC12/RC13 smoke and micro-project outcomes remain historical diagnostics. RC14's historical local checks and smoke are recorded in [`PROJECT_STATE.md`](PROJECT_STATE.md). The frozen protocol still requires paired A0/A1/A2 evidence, non-compensatory safety gates, external isolation review, and three usable independent Agent families. Locked qualification is **NOT RUN**; empirical qualification and Stable remain **NOT ACHIEVED**. Development smoke is not release evidence.

License: Apache-2.0.
