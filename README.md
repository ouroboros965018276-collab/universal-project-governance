# 通用项目治理 | Universal Project Governance

**一个面向持续项目维护的、模型无关的单体 Agent Skill。**

Universal Project Governance 把“实现功能”与“清理、技术债治理、当前状态文档、时序、验证和交接”绑定为同一个完成生命周期。它的目标不是替代工程师或其他专业 Skill，而是确保每一次项目修改之后，受影响范围仍然保持清晰、当前、可验证、可追溯、可维护，并且下一位工程师或 AI 可以在没有隐藏聊天上下文的情况下继续工作。

> 当前版本：**2.0.0-rc.2**  
> 当前状态：**预发布候选 / Release Candidate — NOT STABLE**  
> 仓库状态：在全新仓库中重新建立，旧项目历史不继承。

## 核心原则

这个项目坚持一个简单但严格的定义：**修改成功不等于任务完成。** 一个项目修改只有在适用的五类闭环都完成后才可以宣布完成：

1. **Behavior / 行为闭环**：用户要求的结果实际成立。
2. **Cleanup / 清理闭环**：被替代、重复、过时、临时的残留已经移除或有明确理由保留。
3. **Truth / 真值闭环**：规范文档与当前项目现实一致，不把过时历史混进当前状态。
4. **Evidence / 证据闭环**：重要结论由与结论相匹配的测试、检查、搜索、构建或运行证据支持。
5. **Continuity / 连续性闭环**：模块目的、关键约束、最近一次与上一次有意义的变化，以及交接信息可以从项目自身恢复。

它仍然是**一个 Skill**。维护、重构、技术债、文档守护、时间轴、验证与交接并不是独立 Skill，而是同一治理生命周期的不同责任面。

## 为什么采用“单 Skill + 渐进披露”

`SKILL.md` 保持为紧凑的核心路由与不可变原则；详细规则放在 `references/`，只有任务真正涉及某一类治理时才加载。这样不会把数万 token 的规则常驻上下文，同时不会减少任何应履行的治理责任。

> **Progressive disclosure changes what you load, not what you owe.**

## 仓库结构

```text
.
├── README.md
├── AGENTS.md
├── PROJECT_STATE.md
├── MODULE_MAP.md
├── DECISIONS.md
├── CHANGELOG.md
├── PUBLISHING.md
├── SECURITY.md
├── CONTRIBUTING.md
├── LICENSE
├── .github/workflows/validate.yml
├── audits/
├── evals/
├── tests/
├── tools/
└── universal-project-governance/     # 真正可安装的单个 Skill
    ├── SKILL.md
    ├── LICENSE
    ├── references/
    ├── assets/
    └── scripts/
```

仓库层负责开发、测试、审计和发布；`universal-project-governance/` 是唯一可安装 Skill。这样可以避免把 CI、审计记录、开发测试等仓库维护资产复制进用户项目，同时保持 Skill 本身自包含。

## 安装（预发布阶段）

仓库仍为 Private 时，需要对该仓库有访问权限。公开前会重新验证公共安装链路。

```bash
npx skills add <owner>/universal-project-governance --skill universal-project-governance
```

目标 Agent 可由 Skills CLI 的 `--agent` / `-a` 参数选择。正式发布文档只会使用已在 CI 中实际验证过的安装路径。

## 质量门禁

预发布 CI 会执行：

- 官方 `skills-ref` 规范校验；
- Python 3.8 / 3.11 / 3.13 helper 实机测试；
- Skill bundle、链接、Frontmatter、版本与许可证一致性检查；
- 安全静态审计与 secret-like 内容扫描；
- deterministic package 重建；
- `skills` CLI 本地发现/安装；
- 从当前 GitHub 仓库进行远程发现/安装；
- 本项目自身的 PROJECT_STATE / MODULE_MAP / DECISIONS 治理验证。

这些只能证明结构、工具、安装与一部分安全属性。**Stable 发布还必须额外通过真实 Agent 的触发测试和有 Skill / 无 Skill 行为对照评估。** 不会把静态测试冒充行为有效性证明。

## 技术债规则

默认可证明的声明是：

> **No known unmanaged technical debt was introduced or knowingly left in the affected scope.**

除非做过项目级审计，否则不会把局部检查夸大为“整个项目零技术债”。当任务明确要求受影响范围 `zero unresolved debt` 时，任何未解决 exception 都阻塞完成。

## 与其他 Skills 共存

它不取代代码库发现、框架、数据库、设计、部署等专业 Skill。专业 Skill 负责领域工作流，本 Skill 负责变更后的项目状态完整性。若其他 Skill 拥有固定输出命名空间，本 Skill 必须尊重所有权，复用事实而不是建立第二份真值。

## 许可证

Apache License 2.0。见 [`LICENSE`](LICENSE)。
