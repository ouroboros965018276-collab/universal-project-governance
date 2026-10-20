# 发布与测试冻结门禁

当前候选：**3.0.0-rc.20 — Task Context and Complete Change Discipline**。

RC20 从已合并的 RC19 `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9` 开始。当前发布、验证和安装事实统一见[项目状态](PROJECT_STATE.md)；[RC19 安装验收](audits/rc19-installation.audit.json)是历史基线，不能验证 RC20。候选仍需自身的编译、回归、导航、完整性、打包及安装验收。规则来源比较保留每次注册调用、失败和 unknown 用量围栏；静态检查或更短文档都不证明净收益。Stable 仍须通过原正式资格门禁。

## RC20 本轮工程验收范围

2026-10-20，维护者明确改为复用既有实测、只做必要校准和关键工程验收后发布 RC20；不再以扩大付费对照为本次 RC 合并前提。验收必须覆盖当前源生成一致性、关键状态生命周期回归、整仓回归、仓库门禁、CI、默认分支身份及本地安装。Insight 的状态修复须保留历史、未知项和未完成状态。旧实验结果、失败判据和成本保持不变；本次接受的是有边界的工程升级，独立模型净收益仍未建立，Stable 门槛不变。

## 历史 RC18 证据

RC18 的产物评分修正、测量范围、失败、费用、模型身份及资格限制保留在[不可变测量审计](audits/rc18-real-evaluation.audit.json)和[项目状态](PROJECT_STATE.md)。原始[配对测量](qualification/pilots/rc18-native/paired.summary.json)、[中止的 v1](qualification/pilots/rc18-native/round-v1.summary.json)及[v2 注册协议](evolution/protocol/rc18-native-development-v2.json)继续保留；发布流程不维护第二份历史结果摘要。产物修复不能证明真实工具执行或跨 Agent 交接，历史结果不替代当前候选验收或正式资格。

## 真实 Agent 测试前的工程门禁

以下检查均须通过；`python` 代表已验证的 Python 执行入口：

```bash
python compiler/compile_governance.py --check
python tools/governance_lint.py .
python tools/validate_qualification.py .
python tools/qualification_freeze.py . --check
python tools/validate_repository.py .
python tools/validate_skill_bundle.py universal-project-governance
python universal-project-governance/scripts/validate_integrity.py universal-project-governance
python tools/security_audit.py .
python tools/validate_navigation.py .
python -m unittest discover -s tests -v
```

CI 还须通过 Linux Python 3.8/3.11/3.13、离线演化 Python 3.10/3.13、Windows Python 3.11/3.13、上游 Agent Skills 校验、本地生命周期安装/卸载、干净 Codex 目标安装、确定性打包，以及晋升后的默认分支安装验收。

## 正式真实 Agent 锁定门禁

当前资格指纹下的一轮不可变结果必须满足全部不可补偿门禁。先验收注册轮次、冻结身份、schema 有效的隔离执行、匹配的模型/适配器/宿主条件及保留字节；被拒输入不得进入发布推断。分析器以 1 表示 FAIL、2 表示 MORE_DATA，均不晋升 Stable。

1. 锁定场景、Agent 和实验条件完整覆盖；
2. 项目部署完整性与完成报告；
3. 评分器变异敏感性；
4. attention-control 有效性；
5. 类别特定的关键安全；
6. 越界控制及独立 `local_guard`、`structural_guard` 暴露与置信界限；
7. 核心任务非劣；
8. 治理增益；
9. 交接恢复与退化减少；
10. 触发精确率与召回率；
11. token、时间、工具、任务产物和受管文件效率；
12. 明确置信区间语义下的分组泛化。

## 正式推断

主要置信区间使用预注册的 Agent family → scenario → pair/repetition 分层 bootstrap。直接报告分组证据；泛化 PASS 表示已建立预注册的严重反转判据，不默认为每组收益显著。

## 灰测证据

个人和朋友灰测可导出 `upg-field-test-reports.json`，它是诊断证据，不能替代锁定资格。Stable 前须明确决定保留或移除报告能力。关闭路径已可执行：新绑定不创建 ledger，report/export 不可用。退出前须先导出并清理已有非空 ledger；`remove` 在历史仍存在时拒绝继续，不静默丢弃记录。

## 冻结规则

当前候选统一生成 `qualification/FREEZE.json` 后，结果轮中不得修改冻结面；变化需要新指纹。新 Skill+plan 投影的编译契约与旧专用收集器分开验证，不放宽旧冻结实验的 validator，也不修改其历史审计。
