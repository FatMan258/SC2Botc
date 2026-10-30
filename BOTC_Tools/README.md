# BOTC 规范化工具链

这套工具用于绕开银河编辑器的脚本粘贴步骤：保留原地图的触发器、地形和资源，只替换
`MapScript.galaxy` 中的自定义脚本区段，输出新的测试地图。

工具不会自动创建备份，也不会修改 `BOTC_项目记忆.md`。

## 环境

- Python：`py -3`、`python`，或通过 `BOTC_PYTHON` 指定解释器
- StormLib：`BOTC_Tools\vendor\StormLib.dll`
- 正式脚本：仓库不提供完整地图脚本，必须通过 `BOTC_SCRIPT` 指向本机脚本
- 基础地图：通过 `BOTC_MAP` 指定，仓库不提交 `.SC2Map`
- UI 资源：通过 `BOTC_UI_MOD` 指定
- 构建输出：默认仓库根目录的 `build/`

路径可以通过环境变量覆盖：

```powershell
$env:BOTC_MAP = "C:\path\to\base.SC2Map"
$env:BOTC_SCRIPT = "C:\path\to\BOTC_脚本_粘贴用.txt"
$env:BOTC_UI_MOD = "C:\path\to\UIHIDE55.SC2Mod"
$env:BOTC_BUILD_DIR = (Join-Path $PWD "build")
$env:BOTC_SC2_ROOT = "C:\Program Files (x86)\StarCraft II"
```

如果 Python 不在 `py` 或 `PATH` 中，可设置 `BOTC_PYTHON`，或创建不会提交的
`BOTC_Tools\python.local.cmd` 并设置该变量。

StormLib 固定为官方 v9.40 x64 版本，版本、发布包校验值和 DLL 校验值记录在
`BOTC_Tools\vendor\StormLib-VERSION.txt`。

## 常用命令

可以直接使用批处理入口：

```powershell
BOTC_Tools\botc.cmd inspect
BOTC_Tools\botc.cmd check
BOTC_Tools\botc.cmd build
```

等价的完整命令：

```powershell
py -3 BOTC_Tools\botc.py inspect
py -3 BOTC_Tools\botc.py check
py -3 BOTC_Tools\botc.py build
py -3 BOTC_Tools\botc.py test "build\地图.SC2Map"
```

`test` 会从 `DocumentInfo` 自动识别 `Void.SC2Campaign` 并传入 `-meleeMod Void`，
默认观察 90 秒，至少观察 65 秒后才会报告结果。

如果画面停在网易账号登录或“无法运行游戏”，说明直接启动没有继承平台登录态；
先登录 Battle.net 再测试。线上依赖（例如 `bnet:UIHIDE/1.4/188066`）在登录前不会解析。
工具报告 `ALIVE` 只表示进程存活且没有新的 `ScriptError`，仍需要目视确认地图画面。

`build` 会先运行源码检查，再复制基础地图、替换自定义脚本、回读校验并输出新地图。
默认还会从 `BOTC_UI_MOD` 指定的 SC2Mod 解包并内嵌隐藏 UI 文件，同时删除
`bnet:UIHIDE/...` 或 `file:...UIHIDE...` 依赖。基础地图不会被修改。

只有明确需要保留线上 UI 依赖时才使用：

```powershell
BOTC_Tools\botc.cmd build --no-embed-ui
```

创建角色规格：

```powershell
py -3 BOTC_Tools\botc.py role new --index 148 --name "新角色" --team townsfolk --alignment good
py -3 BOTC_Tools\botc.py role list
py -3 BOTC_Tools\botc.py role audit BOTC_Tools\role_specs\role_148.json
```

一句话角色草稿使用受约束 DSL，不由模型直接生成 Galaxy：

```powershell
BOTC_Tools\botc.cmd design prompt "每个夜晚，你要选择一名存活玩家：你得知他是否是爪牙。"
BOTC_Tools\botc.cmd design validate BOTC_Tools\role_specs\role_dsl.example.json
BOTC_Tools\botc.cmd design compile BOTC_Tools\role_specs\role_dsl.example.json --out role_plan.md
```

详细设计见 `BOTC_Tools\ROLE_DSL.md`。

阵营代号：

| 名称 | 代码 |
| --- | --- |
| townsfolk | 0 镇民 |
| outsider | 1 外来者 |
| minion | 2 爪牙 |
| demon | 3 恶魔 |
| legend | 4 传奇 |
| journey | 5 奇遇 |

## 新角色标准流程

1. 创建 JSON 规格，先确定索引、阵营、行动类型、目标数、夜序和板子归属。
2. 接入 `g_roleName`、`g_roleTeam`、`g_roleAlign`、`g_roleTag`、`g_roleTargets`、`g_roleAct`。
3. 接入 `g_noAllFirst`、`g_noAllOther`；被动或触发型角色不要硬塞进普通夜序。
4. 接入能力文本、详情页区间、图标和资源文件。
5. 新增 token 时同时接 `g_tokName`、`g_tokShort`、`g_tokIcon`、`g_tokRole`、专属死亡 token 和所有清理路径。
6. 主动能力必须走统一能力层：真身、拥有能力、是否生效、实际生效座位分开判断。
7. 身份变化统一走 `BOTC_SetSeatRole()`，离场清理统一走 `BOTC_SourceGoneCleanup()`。
8. 检查换座位、换说书人、第二局重置、中毒、醉酒、死亡、取消、无效目标和多面板并发。
9. 运行 `botc.py check` 和 `role audit`，通过后运行 `botc.py build`。
10. 用 `botc.py test` 启动构建产物，检查是否产生新的 `ScriptError.txt`。
11. 用构建产物进游戏验收，不直接用编辑器保存自动构建地图。

## 角色规格审核

`role audit` 会检查：

- 索引、名称、阵营和阵营倾向。
- 目标数、行动类型、首夜和其他夜晚顺序。
- 能力文本和详情页入口。
- token 槽位及其角色绑定。
- 专属死亡 token。
- 固定板子中的登记情况。
- 规格里声明的必备函数和实现符号。
- 角色图标是否存在于当前地图包。

规格文件是验收契约，不是自动生成角色逻辑的魔法文件。复杂能力仍应人工实现，再通过审核。

## 禁区

- 不要把整个 `MapScript.galaxy` 替换为 `BOTC_脚本_粘贴用.txt`。
- 不要在采用直写构建后随意让编辑器重存整图。
- 不要把 Trigger XML 生成路线和自己的正式脚本路线混用。
- 新角色索引一旦超过 147，必须同步所有角色数组、扫描循环和索引表。

## 自检

```powershell
py -3 -m unittest discover -s BOTC_Tools\tests -v
```
