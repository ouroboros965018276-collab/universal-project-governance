# Git 自动接管与阶段保存

Git 检查点用于保存已验证的有意义阶段，减少中断后丢失工作边界的风险。它支持已有仓库、无 `.git` 项目和尚无首个提交的仓库。未调用 `begin/finish` 的宿主可以在明确前台项目会话内使用观察器；没有可靠会话结束信号时只执行有限检查点／单次观察，不启动独立常驻进程。当前验证与交付事实见 [PROJECT_STATE.md](../PROJECT_STATE.md)，不能从本说明推断已安装或已通过 CI。

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
python scripts/project_tool.py git-watch /path/to/project --action session --command editor --wait /path/to/project
python scripts/project_tool.py git-watch /path/to/project --action status
python scripts/project_tool.py git-watch /path/to/project --action stop
```

配置只保存选择。`session --command` 是前台会话入口：命令必须等待实际项目会话结束（示例 `editor --wait` 需替换为宿主真实支持的入口）。仅返回启动成功、随后把 UI 分离的启动器不能作为会话结束信号。前台会话所有者持有唯一生存凭据，宿主不继承观察器管道或受强制终止的容器。宿主退出或会话所有者异常退出时，观察器、监督和其原生校验／Git 包装子树退出；再次明确进入新的前台会话时恢复保留的配置／基线。

### 宿主适配入口

三个入口共享同一原生会话所有者、停止与恢复实现：

| 宿主能力 | 入口 | 结束信号 |
|---|---|---|
| 本机官方 Codex CLI | `--action session --host codex-cli --executable /verified/path/to/codex` | 本次前台 CLI 退出 |
| 等待实际项目关闭的终端／编辑器命令 | `--action session --command editor --wait /path/to/project` | 已核验等待命令退出 |
| 能持有项目专用子进程管道的 IDE、插件或客户端 | `--action session --host stdin`，子进程 stdin 使用项目专用管道 | 当前项目的全部写端关闭产生 EOF |

Codex 适配器只启动既有可执行文件，固定使用 `--no-daemon --no-alt-screen --cd <project>`，不传提示词、配置覆盖或守护命令；缺少入口时在修改绑定前失败。不自动安装 CLI。真实 CLI 验收与桌面 GUI 验收分别记录，不能互相替代。

运行时只能验证 stdin 是管道，专属归属由调用方保证。管道适配由宿主为每个活跃项目创建并持有；只适用于拥有可靠项目结束回调的集成。关闭项目时关闭管道，重入时重新调用入口；不得用跨项目共享连接、常驻客户端或永不关闭的终端 stdin 代替项目生存信号。输入按有界块丢弃，不解析或记录提示词、心跳或会话内容；只认 EOF，读取异常先收回观察能力再报告失败。EOF 不需轮询宿主进程。此入口提供可执行的通用适配契约，不能自行给未提供信号的宿主增加该能力。

宿主入口必须提供真实项目级开始与结束信号；回答结束、取消订阅或进程名推测不构成项目关闭。桌面端只有提供可靠入口／结束信号后才能验收。适配器不注入会话钩子、App Server 配置或宿主全局设置。

没有该前台能力时，`start` 返回 `session-required` 且不创建进程；普通 `ensure/install/git-configure/recover` 不会分离启动观察器，不猜测父 PID、进程名或编辑器关闭事件。已接入 `begin/finish` 的宿主继续按原生命周期保存；其他宿主可用有限的 `--action tick`。这不等于已为任意编辑器提供适配器。没有宿主全局配置、开机／登录项、任务、服务或系统权限变更。

`stop` 持久化当前停止意图，同一活跃会话不会复活。新的 `session --command` 本身是一次明确启动；普通接手入口不是。状态心跳只代表最近观察，不是永久存活保证。

候选来自实际允许范围的差异。开始前已有的脏文件留给原所有者；观察器等待字节稳定及冷却期，再执行配置的校验。校验在治理锁外运行；发布前重查所有权、手工工作流、HEAD、范围与字节，helper 再核对相同已校验来源。校验失败采用有界退避；相同内容不会每轮重跑，显式 `--action tick` 可立即再检查。输出仅保留摘要、退出码和截断标志，在活跃会话内，超时后的包装进程继续持锁直到实际命令结束，防止重叠；会话结束则由该会话容器／生存凭据终止观察器子树，原事务日志保留供下次核对。输出有界保留。配置的命令按参数执行、不经 shell；观察器自身不调用模型，用户自配命令的行为由配置决定。

活跃手工工作流优先，观察器让位；治理写锁暂忙时退避后继续。相同分支的外部提交必须能证明是快进，观察器才跟随新基线；回退、改分支或删除 HEAD 需要明确重配。已发布但回执中断的检查点沿用原事务恢复，不伪造新的校验；提交期间新出现的有效改动留给下一阶段。明确停止或重配后不会再启动下一条校验；会话结束撤销校验和发布能力，旧会话校验不能在新会话发布。它不伪造任务完成报告或另建治理账本。配置和有限运行状态保存在原 `.governance/upg.json` 的 `git_checkpoint.watcher`，无默认推送。分离 HEAD、稀疏／分离索引、进行中的 Git 操作、自定义钩子不适用或无法证明安全的状态明确阻止。

## 项目会话内的异常恢复

前台会话仍存活时，所有者只监测自己持有的宿主／监督进程对象；监督进程自身异常退出也会在本会话内按有界退避补建，不必等下次项目入口。监督正常时阻塞等待工作进程，不另行扫描 Git或每轮写心跳；工作进程异常退出后仍由原监督和系统锁恢复，复用范围、校验、冷却和去重。

Windows 使用本次会话拥有且不可继承的关闭即终止 Job；首监督进程先停在门控处，归属成功才执行业务，无法建立归属则不启动无保护进程。POSIX 首监督进入独立会话／进程组，成员只在验证过的自身组内处理生存管道 EOF。所有者不需要注册系统服务，也不会为了恢复观察器在会话结束后留守。用户原生命令主动脱离进程组的后代不属于通用 POSIX 保证，不能宣称任意第三方程序都可被收回。

会话结束时先关闭生存能力、终止所拥有子树并核对原生锁释放，再清空当前会话 PID／令牌；所有者硬退出后的元数据可由下次入口在证实锁已释放后收束。物理进程退出与 JSON 状态清理分别验收。未知遗留进程／锁不按裸 PID 强杀，也不删除锁文件来伪造释放。

配置与有限运行状态仍在原 `upg.json`，不生成第二套当前状态。新写入使用独占、刷盘核对的唯一临时文件，异常遗留候选不会阻止后续写入，也不会成为当前状态；未知旧版固定 `.tmp` 仍会阻止。治理移除需等待原生命令结束并持有相关锁，再删除绑定。进程硬退出恢复与断电持久性是不同能力；journal 无法证明时安全阻止，不声称断电无损恢复。

## 已接入的工作流与恢复

`begin` 保存真实基线，`finish` 对声明文件执行有效差异识别。普通 partial 阶段按间隔合并；完成或显式 `git_boundary: handoff/risk` 收束。普通交接文档更新不绕过冷却。已延期事件和无变化事件均固定身份，不能用旧校验提交后来新字节。

`committed` 表示核实提交；`unchanged/duplicate/disabled` 不新增提交，`deferred/cooldown/waiting` 仍在等待，`blocked` 需要处理。阶段保存不等于全部功能验收。原生索引锁及分支 CAS 保护并发工作；本版以操作系统独占锁证明旧进程及其原生命令已退出，再恢复同一事务；索引锁先持久化归属后原子发布。旧版本无归属证明的锁或无法证明的中断结果仍需所有者核对，不能直接删除锁当作修复。

规范默认值在 [治理模型](../governance-src/model/governance-model.json)，实现为 [生命周期](../governance-src/runtime-scripts/project_tool.py)、[Git helper](../governance-src/runtime-scripts/git_checkpoint.py) 、[观察器](../governance-src/runtime-scripts/git_watch.py) 、[进程锁](../governance-src/runtime-scripts/process_guard.py)与[会话生存能力](../governance-src/runtime-scripts/session_lifetime.py)。本地 Git 校准只验证这些确定性行为，不建立模型收益或正式资格。
