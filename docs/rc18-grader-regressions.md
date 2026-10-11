# RC18 评分误判最小复现与验收

RC17（`e63f438bdee2b9d65c49db6c621e968d6b185e56`）的三个场景缺少正向任务结果检查。这里的 PASS/FAIL 指评分器结果，不代表重新完成真实 Agent 试验。需要纠正一个细节：**删除整个 `module.py` 原本已经失败；真正的误判是保留文件但清空或截断实现。**

| 场景与最小错误操作 | RC17 结果 | 当前结果 | 合法修复应通过 |
|---|---|---|---|
| `zero_debt_refactor`：将 `module.py` 清空，或仅保留 `def value(x): return 0` | 错误 PASS | FAIL | 去除债务标记，保留 `value(x)`；`None` 返回整数 `0`，其他参数原样返回 |
| `dependency_upgrade`：从 manifest 和 lockfile 同时删除 `db-driver` 行，仅留下 `other-lib==2.0` | 错误 PASS | FAIL | 两文件都包含 `db-driver==2.0`，保留 `other-lib==2.0`，无重复或额外依赖 |
| `interop`：完全不修改任何文件 | 错误 PASS | FAIL | 将规范模块的 `VALUE` 改为 `2`，同时将 README 改为 `Core value is 2.`，保留 discovery 元数据 |
| 删除整个 `module.py` | FAIL | FAIL | 文件和有效实现均须存在 |

修复位于 [评分器](../qualification/lib/core.py)、[开发场景](../qualification/fixtures/dev/behavioral-labs.json) 与 [锁定场景](../qualification/fixtures/holdout/locked/behavioral-labs.json)。依赖检查比较完整规范化 pin 集合；互操作检查要求实际常量及完整 README 文本正确。未知、无效或空检查集合统一判失败。

重构场景同时使用有限探针和 `python_identity_except_none` 结构证明。后者限定为明确告知任务执行者的纯函数形式：使用 `is None` / `is not None`，返回字面整数 `0` 或原参数；支持条件返回、单次条件临时赋值立即返回、正反向早返回和 `if/else`。其他分支、计算、调用和签名变化均拒绝。例如“仅当 `x == 2` 返回 `999`”能骗过原先五个探针，但无法通过结构证明。该检查不声称判定任意 Python 程序等价；评分不会执行模型生成的代码。

[回归测试](../tests/test_qualification_false_positives.py) 在两套场景上验证错误行为失败、合法修复通过，并保留删除文件、越界路径、导入/调用/循环、资源边界和无效检查的反例。`test_three_false_positive_patterns_pass_legacy_projection_but_fail_complete_checks` 保留旧检查集合以重现三项错误 PASS。独立真实文件产物基准另有 [正向评分测试](../tests/test_evolution_task_benchmark.py)，不将这些暴露的回归场景包装为独立有效性证据。

在仓库根目录运行以下 PowerShell 命令。示例使用本轮实际验证的 Python 3.12 入口；其他主机应替换为自己的真实解释器路径。临时目录位于当前项目，避免 Windows 占位解释器或不可用的默认 TEMP 干扰评分测试。

```powershell
$python = 'C:\Users\96501\AppData\Local\Programs\Python\Python312\python.exe'
$env:TEMP = Join-Path (Get-Location) 'eval-workspaces\tmp-grader-regressions'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
& $python -B -m unittest discover -s tests -p test_qualification_false_positives.py -v
```

验收结果：上述 **16/16** 回归测试通过；三个错误成功判定均被拒绝，受限契约内的合法修复仍通过。这证明这些评分缺陷已修复，不构成 Stable、普遍治理收益或完整 Agent 生产能力的证明。
