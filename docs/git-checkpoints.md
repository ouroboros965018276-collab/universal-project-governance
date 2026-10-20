# Git 自动接管与阶段保存

RC20.4 支持已有仓库、无 `.git` 项目和尚无首个提交的仓库；一次配置后，独立观察进程可处理未调用 `begin/finish` 的编辑器或 Agent。当前验证与交付事实见 [PROJECT_STATE.md](../PROJECT_STATE.md)，不能从本说明推断已安装或已通过 CI。

## 初始化与范围

用已验证的 Python 执行入口运行已安装或生成包中的脚本：

```bash
python scripts/project_tool.py git-configure /path/to/project --enable --allow-path src --allow-path tests --allow-path README.md --status-path PROJECT_STATE.md --min-interval-seconds 300
```

Git 默认关闭；显式启用非空范围后，`bootstrap: true` 允许在指定项目根创建自己的 `.git`。即使项目在父仓库中，也不采纳或提交父仓库；初始化核对父 HEAD、索引和配置未改变。`--no-bootstrap` 可禁止初始化。缺 Git 程序、权限或明确作者身份时报告阻止，不安装工具、不猜身份、不修改全局配置。

已有内容可在首次明确范围内采纳；校验覆盖最终字节，初始观察保留原哈希。已有暂存内容仍受保护：不把无关暂存带进首提交，目标本身已暂存时阻止。首提交通过原生 Git 钩子／签名、私有上下文及零旧值 CAS 产生，重试不盲目重建。

`--allow-path`、`--status-path` 可重复。允许路径是相对文件或目录；`.` 明确允许整个项目。状态路径精确排除，`.governance/` 始终排除；不要把时间戳文件当作阶段成果。默认冷却 300 秒。符号链接、子模块、忽略文件、常见密钥名称、冲突和不支持的高级仓库模式仍会阻止，不声称能辨认所有敏感内容。

## 未接入生命周期的宿主

观察器直接检查项目文件和 Git，无需宿主逐次调用工作流。创建项目自己的配置 JSON，使用已核验的本地校验命令；下面的示例只检查 Git 差异格式，不能当作功能验收：

```json
{
  "enabled": true,
  "poll_seconds": 5,
  "quiet_seconds": 15,
  "validators": [
    {"argv": ["git", "diff", "--check"], "timeout_seconds": 30}
  ]
}
```

```bash
python scripts/project_tool.py git-watch /path/to/project --action configure --input /path/to/watch-config.json
python scripts/project_tool.py git-watch /path/to/project --action start
python scripts/project_tool.py git-watch /path/to/project --action status
python scripts/project_tool.py git-watch /path/to/project --action stop
```

配置只保存选择；`start` 确认同令牌工作进程握手后才报告运行。启动器退出后，后台进程继续观察。普通激活入口 `ensure` 可恢复已配置且未显式停止的观察器。`stop` 合作撤销令牌，不按裸 PID 强杀其他进程；重启继续使用保留的基线。状态中的心跳是最近观察，不是永久存活保证。异常退出由下述项目会话监督恢复；系统启动配置保持不变。

候选来自实际允许范围的差异。开始前已有的脏文件留给原所有者；观察器等待字节稳定及冷却期，再执行配置的校验。校验在治理锁外运行；发布前重查所有权、手工工作流、HEAD、范围与字节，helper 再核对相同已校验来源。校验失败采用有界退避；相同内容不会每轮重跑，显式 `--action tick` 可立即再检查。输出仅保留摘要、退出码和截断标志，超时后守护包装进程继续持锁直到实际命令结束，防止未结束的校验与下一轮重叠；输出有界保留。配置的命令按参数执行、不经 shell；观察器自身不调用模型，用户自配命令的行为由配置决定。

活跃手工工作流优先，观察器让位；治理写锁暂忙时退避后继续。相同分支的外部提交必须能证明是快进，观察器才跟随新基线；回退、改分支或删除 HEAD 需要明确重配。已发布但回执中断的检查点沿用原事务恢复，不伪造新的校验；提交期间新出现的有效改动留给下一阶段。停止或重配后，当前校验可结束，但不会再启动下一条。它不伪造任务完成报告或另建治理账本。配置和有限运行状态保存在原 `.governance/upg.json` 的 `git_checkpoint.watcher`，无默认推送。分离 HEAD、稀疏／分离索引、进行中的 Git 操作、自定义钩子不适用或无法证明安全的状态明确阻止。

## 项目会话内的异常恢复

进入已配置项目的 `ensure` 入口，或主动执行 `git-watch --action start`，才启动项目内监督进程。它正常时阻塞等待工作进程退出，不另行扫描 Git，也不每轮写心跳；工作进程异常退出后才按有界退避恢复，复用原范围、校验、冷却和去重。没有开机／登录启动项、系统计划任务、宿主全局配置或付费模型调用。

明确 `stop` 持久化停止意图；后续项目入口不擅自拉起，`start` 才恢复运行意图。原校验或 Git 命令仍持有系统锁时，恢复等待。本次系统会话首次项目入口或明确启动前不运行。启动命令或编辑器退出不会自动停止独立观察器；需要明确 `stop`，不假设宿主提供关闭事件。系统重启后不自行启动；监督进程自身退出后，由下一次项目入口／明确启动恢复监督。可用 `git-watch --action recover` 显式执行同一安全恢复检查。

配置与有限运行状态仍在原 `upg.json`，不生成第二套当前状态。新写入使用独占、刷盘核对的唯一临时文件，异常遗留候选不会阻止后续写入，也不会成为当前状态；未知旧版固定 `.tmp` 仍会阻止。治理移除需等待原生命令结束并持有相关锁，再删除绑定。本版校准覆盖进程硬退出；未验证断电持久性，journal 不可证明时安全阻止，不声称断电无损恢复。

## 已接入的工作流与恢复

`begin` 保存真实基线，`finish` 对声明文件执行有效差异识别。普通 partial 阶段按间隔合并；完成或显式 `git_boundary: handoff/risk` 收束。普通交接文档更新不绕过冷却。已延期事件和无变化事件均固定身份，不能用旧校验提交后来新字节。

`committed` 表示核实提交；`unchanged/duplicate/disabled` 不新增提交，`deferred/cooldown/waiting` 仍在等待，`blocked` 需要处理。阶段保存不等于全部功能验收。原生索引锁及分支 CAS 保护并发工作；本版以操作系统独占锁证明旧进程及其原生命令已退出，再恢复同一事务；索引锁先持久化归属后原子发布。旧版本无归属证明的锁或无法证明的中断结果仍需所有者核对，不能直接删除锁当作修复。

规范默认值在 [治理模型](../governance-src/model/governance-model.json)，实现为 [生命周期](../governance-src/runtime-scripts/project_tool.py)、[Git helper](../governance-src/runtime-scripts/git_checkpoint.py) 、[观察器](../governance-src/runtime-scripts/git_watch.py) 与 [进程锁](../governance-src/runtime-scripts/process_guard.py)。原始付费研究与正式资格不因本地 Git 校准而重写。
