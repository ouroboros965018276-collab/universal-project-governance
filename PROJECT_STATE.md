# Project State

当前候选为 **3.0.0-rc.20 — Task Context and Complete Change Discipline**；默认分支与本地安装仍为 **RC19**，默认提交 `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9`。RC20 尚未合并或安装，真实净收益未建立。观察日期：**2026-10-16 Asia/Shanghai**；精确工作开始时间未知。

## 当前能力与验证

RC20 将表达相关性、完整改动、事实保真和按需读取纳入[规范源](governance-src/model/governance-model.json)。生成核心 **6,737 字节**，保持四组指引、16 项政策、8 项 Hot Path、3 项默认规则及 18 个交付文件。规范身份 `0049006f…`、资格身份 `f78112d7…`。五个上游的版本、许可、适配与排除由[来源清单](third_party/upstream-sources.json)维护，见[鸣谢](THIRD_PARTY_NOTICES.md)。

工程提交 `eaeb8b695d5e1131670fc55cf3fd6a0706b2620a` 的 [11 项 CI](https://github.com/ouroboros965018276-collab/universal-project-governance/actions/runs/38830685586) 全部通过；Linux Python 3.11 完整测试为 **1,087 通过、2 跳过**。[安全扫描优化](audits/rc20-security-scan-pruning.audit.json)已包含在该提交中；本地另有 8 项通过、1 项宿主跳过，实际仓库扫描入口约 4.86 秒。冻结审计中的 CI 待完成文字只描述其记录时点。此前本地完整测试超时和首轮 CI fixture 失败保留在[工程审计](audits/rc20-cli-known-failure-engineering.audit.json)。

[公开 API 工具校准](audits/rc20-managed-api-public-calibration-v4.audit.json)首次独审通过。[四角色首轮失败](audits/rc20-managed-api-phase-calibration-failure-v3.audit.json)保留：同批读写提示使 MiMo 使用占位哈希，被工具正确拒绝。[新四阶段校准](audits/rc20-managed-api-four-phase-calibration-v4.audit.json)改为等待实际读取结果后再修改，两家模型的四项控制首次独审通过：**6 次请求、8,960 个报告 token**，独立字节保全通过。API7 已进入仓库实现，149 项相关测试通过，匹配 CI 全部通过。以上校准不证明任务质量或 UPG 净收益，迟到结算分支仍无真实验证。

[后端 v5](audits/rc20-fixed-backend-controls-v5.audit.json)完成三族固定对照：3 个参考解通过 40 个测试 ID；26 个负例返回检查失败，其中 **6 个触及输出限制，不能算作目标语义缺陷的有效检出**。首次独审和独立字节保全已完成。[v4 首次失败](audits/rc20-fixed-backend-controls-v4.audit.json)仍保留。[原生 CLI v7 首次失败](audits/rc20-native-cli-closed-failure-v7.audit.json)已冻结保全；收据重建的配置不兼容在新源码身份中修正。[CLI v8 公开校准](audits/rc20-native-cli-public-calibration-v8.audit.json)首次独审通过：正常修复及已知验证失败各有 4 次真实工具调用，验证、清理和完成回合用量证据一致，独立字节复核通过；它不证明任务质量或净收益。[六族开发复验](audits/rc20-six-family-fixed-controls-v7.audit.json)首次独审通过：6 个参考实现通过 65 个测试 ID，15 个已知错误或空测试对照返回检查失败；负例类别不能直接算作语义检出，资源标志保留在原审计中。该轮及[MIME 参考首轮失败](audits/rc20-six-family-reference-failure-v6.audit.json)均完成独立字节保全。[正式开发配对驱动](qualification/pilots/rc20-primary/README.md)已纳入仓库：预定 18 个配对块、54 条工作流、66 个角色；源码独审与 18 项新增定向纯校验通过，实际实验尚未开始。跨 Agent 接手、来源消融和独立未暴露验证仍待完成；各轮禁止续跑、重审或修补原证据。

现有开发证据不支持晋升：已曝光 [v6](audits/rc20-paired-real-python-development-v6.audit.json) 的完整组质量为 **5/8**，两组对照各 **7/8**；较低成本包含提前失败，净收益 FAIL。[v11](audits/rc20-stdlib-project-development-v11.audit.json) 留有一次用量未知，首次原始独审 FAIL。[原生 CLI v6](audits/rc20-native-cli-public-calibration-v6.audit.json) 的首次失败同样保留。其他历史数字、成本、VETO 和源码身份只在各自 [audits/](audits/) 中查阅，不绑定当前候选。

合并和安装仍要求完整组质量不劣于两组对照、无严重否决，报告 token 与完整工作流耗时均严格低于两组对照；未知用量、意外中断、缺失耗时或超限阻止有利净收益结论。研究、人工与未观测总成本保持未知；新轮记账完成不清除旧轮未知费用。正式资格 **UNASSESSED**，locked **NOT RUN**，不宣称 Stable。

## 最近一次重要发布：RC19

PR #20 于 **2026-10-13T05:51:50Z** 合并，提交 `a98449ce91e8bc60ae0d58fa584cbef7ab87c058`。原因是诊断 RC18 耗时增加，并补足项目事实恢复与真实工具成本记录；方法是生成运行时、受控合并、逐字节部署和独立安装验收。

[安装审计](audits/rc19-installation.audit.json)于 **2026-10-13T05:58:35.911624Z** 确认 18 个交付文件与合并版本一致，完整性、规划输入和官方新进程发现通过。该时间是验收观察。[独立 B](docs/rc19-tools-independent-v12.md) 与[追加 C](docs/rc19-tools-independent-v13.md) 均不完整，净收益门槛 FAIL；安装成功不改变该结论。后续 PR #21/#22 只修正文档现状，没有改变冻结运行时。

## 上一件重要发布：RC18

PR #19 于 **2026-10-11T21:35:40Z** 合并，提交 `29cf112b4629d6b90504b079e95a5370c206a4cb`。RC18 修复评分器错误成功判定、压缩指令并记录真实开发对照；该轮 token 点估计降低 **3.84511%**、完整回调耗时增加 **23.6975%**，由此引出 RC19 的耗时诊断。范围与原始结果见 [RC18 实测](qualification/pilots/rc18-native/README.md)及[诊断](docs/rc19-latency-diagnosis.md)。

## 接手入口

- 按任务定位实现、契约、消费者和测试：[MODULE_MAP.md](MODULE_MAP.md)。
- 发布及资格：[PUBLISHING.md](PUBLISHING.md)、[qualification/README.md](qualification/README.md)。仓库专用实验适配器不随 Skill 安装，边界见[工程契约](docs/rc20-behavior-contracts.md)。
- 本地未完成工作使用既有 `.governance/handoff.json`；它不随 Skill 交付，也不替代版本化政策或冻结证据。
- 重要历史及设计原因：[CHANGELOG.md](CHANGELOG.md)、[DECISIONS.md](DECISIONS.md)。
