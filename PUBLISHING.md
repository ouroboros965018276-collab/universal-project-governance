# 发布与测试冻结门禁

当前候选：**3.0.0-rc.20.8 — Whole-project Contract Reconciliation**。

发布用于证明当前源码、分发包、GitHub 修订与本地安装相互对应。当前事实统一见[项目状态](PROJECT_STATE.md)，本次报告处置与验收记录见[当前审计](audits/rc20-ocr-report.audit.json)。工程通过不代表独立模型收益或 Stable 资格；本次升级不增加付费实测。

## 工程验收

变更先落到负责的规范源码，统一生成后验证最终字节。检查必须覆盖源生成一致性、状态生命周期、受影响回归、整仓测试、仓库门禁、导航、完整性、确定性打包、CI、GitHub 目标修订与本地安装。

`python` 代表已验证的执行入口：

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

CI 的实际平台、Python 矩阵、上游 Agent Skills 校验和安装任务以[工作流](.github/workflows/validate.yml)为准。只有实际完成的检查可登记为通过；准备失败、平台跳过、未运行与结果未知分别记录。后续影响源码或身份的修改使相应旧检查过期。

Git 检查点须验证允许范围、开始前脏文件保护、冷却、状态噪声与重复排除、初始化与首提交、并发索引/分支保护、完成和显式交接/风险边界，以及钩子失败、中断恢复和前台会话终止。确定性行为使用本地真实 Git/进程校准；不因此调用模型、注入宿主全局配置或增加系统常驻。

工程验收后核对 GitHub 实际提交与 CI，再从目标修订安装并验证本地包字节和项目生命周期。磁盘完整性、宿主发现和新会话实际加载分别记录，不能互相代替。当前发布状态不由本文预先宣布。

## 正式资格

正式资格用于检验跨 Agent 的任务质量、治理效果、安全和成本。结果必须属于同一注册轮次与冻结指纹，满足隔离执行、匹配模型/适配器/宿主身份及原始字节留存要求。被拒输入不进入发布推断；分析器 1 表示 FAIL，2 表示 MORE_DATA，均不晋升 Stable。

全部不可补偿门禁必须通过：

1. 锁定场景、Agent 和实验条件完整覆盖；
2. 项目部署完整性与完成报告；
3. 评分器变异敏感性与 attention-control 有效性；
4. 类别特定关键安全，以及独立 local/structural 越界暴露与置信界限；
5. 核心任务非劣、治理增益、交接恢复和退化减少；
6. 触发精确率与召回率；
7. token、时间、工具、任务产物和受管文件效率；
8. 明确置信区间语义下的分组泛化。

主要置信区间使用预注册的 Agent family → scenario → pair/repetition 分层 bootstrap。直接报告分组证据；不得用其他高分抵消关键失败。完整协议与门槛在[资格入口](qualification/README.md)维护，本文不建立第二份数值配置。

## 状态与证据边界

临时灰测报告是诊断证据，不能替代锁定资格。新绑定默认不创建 ledger；已启用项目的非空 ledger 先导出并核实，再显式清理，移除不得静默丢弃。

`qualification/FREEZE.json` 绑定当前候选的源码、协议、评估器与执行条件。身份变化必须重新生成并重新验证；已完成观察不能改写成新候选的成功。当前树只维护有效契约、当前验收及最新/上一次变更；更早版本通过 Git 历史检索。
