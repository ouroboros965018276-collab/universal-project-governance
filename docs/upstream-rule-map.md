# 上游概念的选择性映射

[上游来源表](../third_party/upstream-sources.json) 是已审阅 commit、文件、许可身份、选用概念、排除行为、UPG 目标、触发和 UPM 验收契约的唯一登记入口。[公开致谢](../THIRD_PARTY_NOTICES.md) 与[既有许可和历史记录](../third_party/notices/README.md)继续保留。

映射记录独立的概念适配，不是运行时规则源。治理语义仍以 `governance-src/model/governance-model.json` 为准；运行时由它编译，不拼接外部 Skill。阅读外部 Skill 不会激活其角色，也不授权工具、网络、凭据访问或安装。

每个 `sources[].selected_files` 条目保留固定 commit 链接和 Git blob 身份；`mappings[]` 将已审阅的文件/章节关联到既有 policy、可选 execution-guidance ID、具体触发和一个验收用例。排除项说明其与完整责任层修改、事实精度、有界证据或用户指令冲突的部分。当前许可与历史/传递性声明分别保留；致谢不代表背书或许可使用无关资产。

## 当前语义承接

四条来源适配的完整表达只在 Skill 中渲染一次；计划保留原基础 policy closure，按需附加模型中的既有工作流块。计划必须配合已加载 Skill 使用；无 helper 时使用 Skill 与手工 index 路由。工作流迁移不是新增来源规则，也不删除 start facts、因果顺序、latest/previous、真实字节回执、未知、验证、清理或交接义务，见[源码职责](../governance-src/README.md#任务投影)。

UPM 用例定义正例与失败条件。`test_references` 是验证入口，不表示新运行已通过；发布审计必须绑定实际执行结果和被测源码。空引用需要补充 fixture 覆盖或明确评审。来源哈希、公开致谢和静态验收都不证明模型质量、token/时间节省、因果收益或正式资格。

## 比较与证据边界

来源消融只移除预注册的新增 execution guidance；核心 policy、既有工作流、真实证据、安全、必要验证和交接义务仍必须保留。前瞻协议须严格绑定当前编译产物；调用失败、费用未知和执行身份缺失都必须保留，不能重放未知调用或将未知费用算零。

提供方报告的模型名和 usage 不证明内部模型身份或全部重试覆盖。不同 tokenizer 的绝对 token 数、API 与 CLI 延时不能直接合并成因果效果；字节计量也不是 token 测量。已暴露的开发目标不能重新称为独立留出任务，失败或无收益结果不授权晋升。
