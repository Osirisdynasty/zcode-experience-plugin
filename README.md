# zcode-experience-plugin

面向 ZCode CLI / 桌面端的经验复用插件：开工建立目标并查经验，收尾把实际执行整理成案卷和条件经验，通过取用结算记录经验是否有效。

本仓库发布用户提供的 **v0.2.0 插件包**及配套讲解。插件源码保留包内原样；包名为 v0.2.0，但 manifest 的 `version` 仍是 `0.1.0`，`exp.query` 协议也仍标 `0.1.0`。安装时以本仓库文件内容为准。它是命令协议、技能与确定性辅助脚本的组合，尚非全自动经验管理服务。

## 为什么要做

会话摘要常保留“最后做成了什么”，却丢掉尝试、失败、方案调整及适用边界。这个插件利用 ZCode 已有的会话数据库，以工单目标组织记录，保留可追溯来源，再提炼可行动、可验证的经验。开工时先核对经验适用条件，收尾时再结算效果，避免把词面相似当作可直接照搬。

完整背景和原作者实例见 [机制、用法与施工手册](docs/design-guide-20261012.md)。其中本机规模、加载计数和 W11/X4 自举实例是原作者讲解中的历史记录，不是所有安装环境的通用保证，也不代表本次发布重新验证了端到端闭环。

## 数据怎么组织

| 对象 | 目录 | 职责 |
|---|---|---|
| W 目标卡 | `orders/` | 开工目标、范围、验收、来源会话锚点，收尾补终态 |
| E 案卷 | `cases/` | 围绕目标组织尝试、反馈、调整、失败与验证证据 |
| X 经验 | `lessons/` | 适用条件、建议、预期效果、验证点、例外、来源与版本 |
| U 取用记录 | `usages/` | 记录经验版本、适用判断、计划变化及采用效果 |
| Q 查询记录 | `queries/` | 检索式、候选与空结果；无经验可用也是合法结果 |

`INDEX.md` 是生成索引；`backlog.md` 是未完成沉淀的待补清单。原始数据库只读；既有 `memories/` 和 skills 不会被此插件自动迁移或替换。

## 具体挂载在哪

```text
~/.zcode/
├── cli/
│   ├── config.json                 ← plugins.dirs 注册插件
│   └── db/db.sqlite                ← 原始会话记录，只读
├── plugins-local/experience/       ← 本仓库 experience/ 的内容
│   ├── .zcode-plugin/plugin.json
│   ├── commands/                   ← 四个斜杠命令协议
│   ├── skills/experience/SKILL.md   ← 体系说明技能
│   ├── hooks/hooks.json            ← Stop 生命周期挂点
│   └── scripts/                    ← 五个 Python 辅助脚本
└── experience/                     ← 各机器自己的经验数据，不在发布包里
    ├── orders/
    ├── cases/
    ├── lessons/
    ├── usages/
    ├── queries/
    ├── INDEX.md
    └── backlog.md
```

挂载链：`config.json → plugins.dirs → experience manifest → commands / skills / hooks`。`hooks/hooks.json` 使用 `${ZCODE_PLUGIN_ROOT}/scripts/settle_check.py`，以 `python` 进程执行，超时配置为 15000ms。

**唯一自动挂点是 Stop。**它检查会话是否已有 W 目标卡，缺失则尝试追加 backlog；不会自动生成 E/X，不会自动执行 `/exp.settle`，不会点击桌面归档按钮，也不修改 `session.time_archived`。Stop 的具体触发时机由所用 ZCode 版本决定，不能直接等同于用户点击“归档”。开工调取与完整收尾提炼由四命令协议驱动。

## 安装

需要已安装并运行过的 ZCode，以及 PATH 中可用的 Python 3。脚本只使用 Python 标准库。

1. 克隆/下载本仓库，将 **`experience/` 目录内容**放到 `~/.zcode/plugins-local/experience/`。也可解压 [原始插件包](dist/zcode_experience_plugin_v0.2.0.zip)：ZIP 自带顶层 `experience/`，解压到 `~/.zcode/plugins-local/`，避免出现 `experience/experience/`。
2. **迁移路径。**当前源码写死了原作者的 `C:/Users/14538/.zcode/`。换用户/机器必须修改下表常量，以及 `commands/*.md` 中的脚本路径；仅修改 config 不够。
3. 在 `~/.zcode/cli/config.json` 现有 `plugins.dirs` 数组追加插件路径，保留其他配置与插件。例如 Windows：

```json
{
  "plugins": {
    "dirs": [
      "C:\\Users\\YOUR_USER\\.zcode\\plugins-local\\experience"
    ]
  }
}
```

这是合并示例，**不要覆盖整个已有配置文件**。配置也可以指向其他绝对目录，但命令内硬编码路径需要同步修改。

| 文件 | 要调整的路径 |
|---|---|
| `scripts/query.py` | `LESSONS_DIR` |
| `scripts/reindex.py` | `EXP` |
| `scripts/timeline.py` | `DB_URI`（保留 `file:` 和 `?mode=ro`） |
| `scripts/verify_chain.py` | `DB_URI` |
| `scripts/settle_check.py` | `DB_URI`、`EXP`（ORDERS/BACKLOG 由 EXP 派生） |
| `commands/*.md` | 命令示例中的绝对脚本路径 |

4. 创建数据目录并初始化 backlog。PowerShell 示例：

```powershell
$experienceRoot = Join-Path $env:USERPROFILE '.zcode\experience'
'orders','cases','lessons','usages','queries' | ForEach-Object {
    New-Item -ItemType Directory -Path (Join-Path $experienceRoot $_) -Force | Out-Null
}
$backlogPath = Join-Path $experienceRoot 'backlog.md'
if (-not (Test-Path -LiteralPath $backlogPath)) {
    @'
# 待补清单

| 会话/单 | 缺什么 | 何时进单 | 状态 |
|---|---|---|---|
'@ | Set-Content -LiteralPath $backlogPath -Encoding utf8
}
```

`settle_check.py` 要求上述表头；缺文件/表头异常会静默跳过，不能只创建空文件。

5. 重启 ZCode，检查命令列表、技能与 Stop hook 是否加载。启动日志在 `~/.zcode/cli/log/zcode-<日期>.jsonl`，可查 `bootstrap.app.startup.plugins.completed`。相对安装前，应多一个插件目录、命令目录、技能目录和 Stop hook；具体计数取决于环境。再执行一次 `/exp.start` 验证真实调用，文件存在不等于加载成功。

## 怎么用

| 阶段 | 命令 | 作用 |
|---|---|---|
| 开工，计划定稿前 | `/exp.start <目标一句话>` | 建 W、查询 X、核适用条件、形成规划引用块 |
| 收尾，终态已定 | `/exp.settle <session_id>` | 读底稿、切单、补 W、整理 E、提炼 X、结算 U/Q、校验引用 |
| 归档前补检 | `/exp.archive <W编号>` | 查 W/E/Q 和引用，缺项进 backlog；U 可为零 |
| 随时查账 | `/exp.query <X编号/W编号/session_id>` | 查来源、取用史、效果与会话归属 |

这些是插件文件定义的命令名；客户端如显示命名空间，以实际命令列表为准。

例如：

```text
/exp.start 修复轮询队列误把频道播报当成工人产物的问题
# 完成施工和独立验证后：
/exp.settle sess_实际会话ID
/exp.archive W实际编号
/exp.query X实际编号
```

开工时先问“当前架构里这个场景存在吗”，再问“适用条件成立吗”。`hit` 仅是候选召回，不能直接授权采用。未知条件保留待核点；没有适用经验就记 Q、照常开工，不编 U。

采用经验要记录 `X@版本 / 匹配条件 / 改变哪步计划 / 验证点`。执行中失效时保留旧引用块，记录原因并形成新版；授权内继续，扩大范围或改变验收才升级处理。

收尾提炼按两个基准过滤：本单 `W.goal` 与原会话目标锚点。离题分支保留案卷，但不进入 lessons；用户明确批准改目标时记录 `approved_goal_change`。当前此项由命令协议指导模型判断，并无独立确定性过滤器。

## 脚本直接使用

在已完成路径迁移的插件目录内运行：

```powershell
python scripts/query.py '修复轮询队列产物接收' --top 5
python scripts/timeline.py sess_实际会话ID --full --out 底稿.md
python scripts/verify_chain.py 案卷.md 经验.md
python scripts/reindex.py --out INDEX-preview.md
```

`reindex.py` 不带 `--out` 时更新真实 INDEX 并备份 `.bak`。`verify_chain.py` 退出码：0 全部通过；1 引用缺失/歧义；2 某文件没有可识别引用。校验仅证明 call/msg/file 找得到，不证明它属于正确会话、正确版本或足以支持结论。`--json` 目前在文字报告末尾追加 JSON，整个 stdout 不是纯 JSON。

## 本机性与当前边界

插件 Python 脚本没有网络调用，经验库保存在本机，发布包不包含个人 W/E/X/U/Q、会话数据库或凭据。提炼协议禁止 headless 自调用和向当前会话之外另发材料。

**这不等于经验内容绝不离机。**如果当班主会话由云端模型处理，读取底稿或经验正文仍会通过当前模型通道发送到远端。严格不离机需要 ZCode 使用本地模型，并限制相关网络出口；本插件没有实现网络隔离或防外发强制机制。

其他已知边界：

- Stop 只查 W 缺失，消息数少于 4 的会话豁免；按 ID 前缀/标题匹配可能误判。fail-open 不阻塞会话，也意味着故障可能静默跳过；不是全链健康检查。
- 开工建卡、目标过滤、经验提炼及版本历史依赖模型执行协议；不是数据库状态机。
- 词面检索依赖手工域词表；纯 bigram 不具备 hit 资格，但仍可能产生 suspect，需核场景。
- 引用校验使用文本 LIKE，仍受 JSON 序列化格式影响；版本存储、编号并发、原子写入和失败恢复尚待工程化。
- 经验数据与代码分开维护。不要把自己的经验目录、数据库、日志或模型凭据提交进公开仓库。

## 仓库内容

```text
experience/                         插件原始源码
docs/design-guide-20261012.md        原作者讲解
dist/zcode_experience_plugin_v0.2.0.zip  原始可下载插件包
README.md                           安装、挂载、使用与边界
```

插件 manifest 声明 `MIT`；原始压缩包未附 LICENSE 正文，本次保留该声明，未补写作者版权归属。
