# 完成前的变更审查与审计

每次修改正常结束前，Agent 都要审查本次修改的部分及受影响消费者，并审计对应验证、范围、重复实现、过时文档与清理残留。局部小改动保持轻量，可在既有最终回复或 VCS 证据中记录结论；非平凡任务使用现有工作流与报告。规则只在[规范模型](../governance-src/model/governance-model.json)定义，本页说明生命周期输入。

`finish` 与直接写入 field report 的新 `complete` 都要求 `completion_review`。旧历史仍可读取，原完成输入的精确重试保持幂等；`partial`、`blocked` 不强制伪造审查成功。报告开关、latest/previous、开始事实与 Git 允许范围保持原契约。

新契约工作流先按[任务生命周期](task-lifecycle.md)完成阶段与原验收，再通过本页最终审查。推进状态、开始约定和原始变更事实各用自己的契约；field report 输入不能直接替代工程执行记录。

## 操作

1. 从当前差异与任务事实确认完整 `changed_files`，包括新增、更新、删除、生成文件和受影响文档。追踪真实调用、数据、配置与异步消费者，不能只凭关键词命中判断覆盖。
2. 审查正确性、契约、安全、异常、重试/幂等与共享写入边界；审计当前验证是否对应最终字节，检查重复、过时与废弃残留。实质改动在可用时使用独立评审，主负责人逐项核实发现。评审一致或哈希相等都不证明行为正确。
3. 修复确认且在授权范围内的问题，重跑受影响验证并重新审查。未解决阻塞项使用未完成状态；范围外风险明确保留，不将局部审查写成全项目清零。
4. 为每个 `changed_files` 路径记录当前 SHA256；已删除文件用 `null`。安装包中的 `scripts/completion_review.py` 可读取当前来源身份，再填写真正完成的审查依据。该命令只读取身份，不执行语义审查，也不生成通过结论。
5. 在原完成输入中加入下列对象，通过已验证 Python 执行 `scripts/project_tool.py finish <project> --input <completion.json>`。必须检查返回结果及 Git 检查点；缺少、过期、遗漏或不安全路径会拒绝新完成。

例如在安装包目录运行，`python` 代表已验证的 Python 执行入口：

```bash
python scripts/completion_review.py /path/to/project --path src/changed.py --path src/removed.py
```

将输出的 `files` 数组放入原完成输入的 `completion_review`，再填写实际审查与审计依据。Windows 可以直接使用已安装脚本的绝对路径及实际项目路径。原工作流的 `workflow_id` 与 `change` 开始事实保持不变，其余必填字段沿用[报告契约](../governance-src/schemas/field-report.schema.json)；此对象不是独立的 `finish` 输入。

```json
{
  "completion_review": {
    "review": {
      "status": "passed",
      "evidence": ["当前差异与受影响消费者的实际审查位置/结论"],
      "findings": []
    },
    "audit": {
      "status": "passed",
      "evidence": ["最终验证记录及范围、重复/过时/残留检查依据"],
      "findings": []
    },
    "files": [
      {"path": "src/changed.py", "sha256": "填写实际当前文件的64位小写SHA256", "executable": 0},
      {"path": "src/removed.py", "sha256": null, "executable": 0}
    ]
  }
}
```

上例是字段说明，不能原样作为完成证据。`capture_sources` 返回 `{path: [sha256, executable] 或 null}`；`executable` 是实际 `stat.st_mode & 0o111`，删除时为 0。`files` 必须与 `changed_files` 一一对应；路径使用项目内规范相对路径，不接受穿越、别名、重复或符号链接。两个结论必须实际通过且没有未解决 findings。证据只保存有界元数据和引用，不放源码、凭据、私人数据或思维过程。

## 证据边界

新完成写入前核对当前字节；启用 Git 时，已审查来源继续交给检查点核验，防止检查后发生的变动被提交。可观测的开始基线用于发现遗漏的 Git 变更；没有可用基线或 Git 时，只能核对声明范围与当前字节，不能宣称自动发现了全部改动。被修改又还原的过程、外部服务写入及运行行为仍需要 Agent 的实际事实与验证。

报告关闭时，紧凑收据保留在既有 latest/previous；开启时复用有界 ledger。不创建新的报告数据库、守护进程或宿主配置。安装验收须实际运行已安装脚本，不能仅凭版本号或复制成功认定生效。相关实现与故障回归见[完成门禁](../governance-src/runtime-scripts/completion_review.py)、[生命周期](../governance-src/runtime-scripts/project_tool.py)、[回归测试](../tests/test_completion_review.py)。

完整完成输入仍受既有 64 KiB 元数据限制；文件身份最多 512 项，每个文件最多 64 MiB，总读取最多 256 MiB。达到边界时按真实、可验证的任务单元完成或保留未完成状态，不能静默截断清单、遗漏变更或编造已审查。无实际内容变化的接触/还原操作、文件系统外的修改和不可读取内容必须在实际审查中明确范围。

若报告已经落盘、绑定尚未完成对账便崩溃，原输入精确重试保留历史观察。发现当前状态已有漂移时，工具返回 `completed: false` 并留下 `completion_review_pending`；此时不提交 Git，也不能宣称当前工作完成。以历史完成事件为父事件开始新的明确工作流，重新审查、验证并覆盖待审路径，直到新完成通过后才解除标记。不能覆盖旧报告、重放未知业务写入或将历史成功当成当前验收。

Git 自动恢复只延续原来已拥有、允许范围内的路径，且须匹配原已验证分支和精确 HEAD；新捕获基线还要再次匹配。身份缺失、切换分支或 HEAD 来源不明时不接管原有改动。若仍有原生 Git journal，先用原阶段输入恢复它，再对账完成记录；工具保留原工作流与 journal，不用新的待审标记掩盖未完成事务。
