# BOTC 说书人地图开发指南

> 本文件是长期维护的工程约定。开始任何修改前先阅读本文件。
> 工具使用说明见 `tools/README.md`；角色 DSL 见 `docs/ROLE_DSL.md`。

## 1. 项目定位

- 项目是星际争霸 II 的《血染钟楼》真人说书辅助地图。
- 智能说书 / AI 说书已废弃，不得恢复自动裁量。
- 玩家 1 通常是说书人，玩家 2..13 是参与者；换座位后说书人可位于任意物理座位。
- 最终验收以游戏内实际效果为准，不使用“代码看起来正确”代替实测。
- 对外输出使用中文，先说结果，少堆实现细节。
- 开源化时不得包含账号凭据、私有 Battle.net 依赖、未授权素材或个人信息。

## 2. 当前状态

- 公开构建基线为 `base/BOTC.map`；其他构建地图默认不提交。
- 旧工作图不得作为当前构建基线。
- 当前地图约有 550 个包内成员，公开构建采用 `MapScript.galaxy` +
  `BOTC_CustomLogic.galaxy` 的分离脚本结构。
- 当前基础地图只依赖虚空之遗战役，UI 文件已经内嵌。
- 当前有 12 张固定板子、动态“自定义剧本”和“全员追忆”板子。
- 136..142、147 是实验性角色；143..146 是全员追忆占位身份。
- `BOTC_DevPlayer()` 固定关闭；【赋予能力】和【发送特定信息】是保留的说书人工具。

## 3. 文件与工具链

### 3.1 正式文件

- 正式脚本：`scripts/BOTC.txt`。
- 新角色测试脚本：`scripts/BOTC_test.txt`。
- 当前基础地图：`base/BOTC.map`。
- UI 依赖源：由 `BOTC_UI_MOD` 指定。
- 构建输出：由 `BOTC_BUILD_DIR` 指定，默认 `work/`。
- 工具目录：仓库内的 `tools/`。

### 3.2 固定环境

- Python：优先使用 `BOTC_PYTHON`，否则使用 `py -3` 或 `python`。
- MPQ 写入：`tools\vendor\StormLib.dll`，固定 v9.40 x64。
- 星际 II：由 `BOTC_SC2_ROOT` 指定，默认使用标准安装目录。
- 游戏日志与测试地图目录由 `tools/botc_config.py` 按当前用户目录解析。

### 3.3 标准命令

```powershell
tools\botc.cmd inspect
tools\botc.cmd check
tools\botc.cmd build
tools\botc.cmd test "构建出的地图.SC2Map"
tools\botc.cmd design prompt "一句话角色描述"
tools\botc.cmd design validate 角色DSL.json
tools\botc.cmd design compile 角色DSL.json --out 角色计划.md
tools\botc.cmd role list
tools\botc.cmd role audit 角色规格.json
```

## 4. 标准开发循环

1. 先精确搜索函数名和关键字符串，只读取命中位置附近的必要代码。
2. 确认本次只处理一个功能或一个 Bug，不顺便恢复已停用功能。
3. 对正式脚本做最小定向修改，不整份重排或格式化。
4. 运行 `tools\botc.cmd check`。
5. 涉及角色时，先维护角色规格，再运行 `role audit`。
6. 运行 `tools\botc.cmd build`。
7. 再运行 `botc.cmd inspect`，核对：
   - `MapScript.galaxy` 存在且大小合理。
   - 自定义脚本首尾标记和初始化函数存在。
   - 只保留预期的依赖。
   - 内嵌 UI 文件和资源存在。
8. 能登录 Battle.net 时运行 `botc.cmd test`，并人工确认实际画面。
9. 检查最新 `ScriptError.txt`、`Alerts.txt`、`UI.txt` 和 `Text.txt`。
10. 确认没有自动创建备份，也没有更新项目记忆。

`test` 报告 `ALIVE` 只表示进程存活且没有新 `ScriptError`，不等于地图已成功显示。
网易账号登录页、Battle.net 未登录或线上依赖未解析时，必须由用户手动确认。

## 5. 解包构建流程

### 5.1 默认路线

- 默认使用 `tools\botc.cmd build`。
- 构建器复制基础地图，定位 `MapScript.galaxy` 中的：
  - `// Custom Script: BOTC_Init()`
  - `// Custom Script Initialization`
- 只替换两者之间的自定义脚本区段，保留编辑器生成的头尾、触发器初始化和 `InitMap()`。
- 不得把整个 `MapScript.galaxy` 直接替换成脚本源文件。
- 写入后必须回读 `MapScript.galaxy`，确认自定义脚本、`InitCustomScript()` 和
  `InitMap()` 都还在。
- 基础地图不得被原地修改；每次输出新的构建地图。

### 5.2 UI 与依赖

- `base/BOTC.map` 已包含构建所需的 UI 文件。
- 公开构建不再读取或修改外部 UI 模块。
- 基础地图只保留虚空之遗战役依赖。
- 修改 UI 时直接更新基线地图，并重新运行构建和实际画面验收。

### 5.3 编辑器边界

- 编辑器仅用于地形、游戏属性、隐藏属性、资源导入、地图信息和平台发布。
- 采用直写构建后，不要让编辑器保存或 Test Document 覆盖正式构建地图。
- 在编辑器修改基础地图后，应另存为新基础图，再重新运行 `inspect` 和 `build`。
- 直接写入方式无法修改 `(attributes)` 等特殊 MPQ 成员时，仍由编辑器维护基础图。

### 5.4 故障回退

只有以下情况才允许临时回到编辑器粘贴：

- 用户明确要求。
- 解包构建器无法写入当前地图格式。
- 需要验证脚本源文件与编辑器编译器差异。

回退后仍要把最终脚本同步回 `scripts\BOTC.txt`，下一次构建继续使用解包路线。

## 6. 修改安全规则

1. 修改前先精确搜索：

```powershell
rg -n -F -m 20 'BOTC_函数名' scripts\BOTC.txt
```

2. 不知道函数名时，先用一个精确界面文字定位，再改用命中函数名搜索。
3. 不整份读取约 2 MB 主脚本，只读取函数体及调用点附近片段。
4. 用花括号范围定位函数体，不用可能重复出现的文本锚点直接替换。
5. 若需要批量替换，完成所有前置替换后重新测量插入位置。
6. 插入后必须验证：
   - 全文 `{}`、`[]`、`()` 配平。
   - 目标函数行号范围正确。
   - 新代码位于函数体或分支的正确层级。
   - 所有局部变量声明在第一条语句之前。
7. 修改 `if` 条件后打印整行人工核对，不能只看括号总数。
8. 检查字符串和注释外的括号深度，不能只做全文计数。
9. 禁止使用会先清空再写的补丁工具修改正式脚本。
10. 不自动创建备份；用户自行管理备份。
11. 不更新 `BOTC_项目记忆.md`，项目上下文由当前仓库和 AGENTS 维护。
12. 旧版 `BOTC_开发手册.md` 只作历史参考。

## 7. Galaxy 与文件格式

- 数组维度写在类型后：`int[14] g_vote;`
- `if`、`&&`、`||` 的条件必须为 `bool`。
- 不支持三元表达式 `条件 ? A : B`。
- `string` 与 `text` 不能隐式混算；界面文字通常需要 `StringToText(...)`。
- `PlayerName()` 返回 `text`。
- 字符串分隔符统一使用直引号，中文内容内使用「」【】。
- 全局变量写在文件开头；后定义函数必须先声明。
- 正式源脚本保持 UTF-8 BOM 和 CRLF。
- 包内 `MapScript.galaxy` 写入时必须去除 BOM，并保持 CRLF。
- 高频逻辑不得在 `BOTC_Tick_Func()` 或每次魔典重绘中遍历全部能力来源。
- 角色扫描上限当前为 147，相关数组长度为 148。
- 每条板子的角色容量为 256，`g_boardRole` 总长度为 4096。

## 8. 座位、观察者与真值

- 物理座位是 SC2 玩家号，用于名字、`PlayerGroupSingle`、踢人、bank、投票和会话。
- 游戏格是魔典上的 13 个逻辑位置。
- `g_who[格]` 表示该格当前由哪个物理玩家操作。
- 格子 1 是说书人格，格子 2..13 显示玩家 `[1]..[12]`。
- `g_lab[格]` 是编号，默认 `格 - 1`，换位时不动。
- `g_seatOn` 记录物理槽位有没有真人，也不得交换。
- 身份与 token 按观察者分别保存：
  - `g_mark[(观察者 * 14) + 格] = 角色索引 + 1`
  - `g_tokOn[((观察者 * 14) + 格) * 256 + token]`
- 游戏判定只读当前说书人的真值行：`(g_teller * 14)`。
- 换座位 / 换说书人后统一调用 `BOTC_AfterSeatChange()`。
- 技能面板换位后必须重新绑定逻辑格，否则点击和确认会失效。
- 判断某格是否为说书人使用 `g_who[p] == g_teller || p == 1`。
- 说话人用 `BOTC_SayToken(物理座位)`；正文座位用 `BOTC_NameStr(逻辑格)`。

## 9. 身份与能力层

- `BOTC_SeatTrueRole()`：真实身份。
- `BOTC_HasAbility()`：是否拥有某能力，来源包括原生、哲学家、食人族、炼金术士、
  科学怪人和说书人赋予。
- `BOTC_AbilityWorks()`：能力当前是否生效。
- `BOTC_AbilitySeat()`：能力实际生效的座位。
- `BOTC_AbilityInPlay()`：能力是否在场。
- `BOTC_SeatImpaired()`：中毒或醉酒。
- 中毒、醉酒和失去能力通常只改变“是否生效”，不阻止玩家打开技能面板。
- 认知覆盖包括酒鬼、提线木偶、疯子、悟道者。
- 显示身份、真实身份和实际能力必须分开。
- 身份变化统一调用 `BOTC_SetSeatRole()`。
- 来源离场统一调用 `BOTC_SourceGoneCleanup()`。
- 新增被动能力必须进入能力层，不能只比较原生角色索引。
- 假声称只能写公开文本和声称状态，不得污染真身份或能力记录。

## 10. 角色索引

| 索引 | 角色 |
| --- | --- |
| 0..12 | 洗衣妇、图书管理员、调查员、厨师、共情者、占卜师、送葬者、僧侣、守鸦人、贞洁者、猎手、士兵、镇长 |
| 13..21 | 管家、酒鬼、陌客、圣徒、投毒者、间谍、红唇女郎、男爵、小恶魔 |
| 22..34 | 祖母、水手、侍女、驱魔人、旅店老板、赌徒、造谣者、侍臣、教授、吟游诗人、茶艺师、和平主义者、弄臣 |
| 35..46 | 修补匠、月之子、莽夫、疯子、教父、魔鬼代言人、刺客、主谋、僵怖、普卡、沙巴洛斯、珀 |
| 47..59 | 钟表匠、筑梦师、舞蛇人、数学家、卖花女孩、城镇公告员、神谕者、博学者、女裁缝、哲学家、艺术家、杂耍艺人、贤者 |
| 60..71 | 畸形秀演员、心上人、理发师、呆瓜、镜像双子、女巫、洗脑师、麻脸巫婆、方古、亡骨魔、诺-达鲺、涡流 |
| 72..82 | 气球驾驶员、失忆者、食人族、寡妇、贵族、巡山人、工程师、渔夫、农夫、魔像、落难少女 |
| 83..89 | 无神论者、精神病患者、灵言师、罂粟种植者、哈迪寂亚、哨兵、圣洁之魂 |
| 90..94 | 赏金猎人、小精灵、告密者、提线木偶、军团 |
| 95..102 | 炼金术士、将军、政客、巫师、哥布林、痢蛭、异端分子、恐惧之灵 |
| 103..113 | 传教士、国王、村夫、异教领袖、半兽人、唱诗男孩、解谜大师、狂热者、堤丰之首、小怪宝、暴风捕手 |
| 114..121 | 修行者、店小二、郎中、变脸师、悟道者、逆臣、帽匠、混沌 |
| 122..129 | 骑士、道士、鸩、女祭司、赶尸人、利维坦、守夜人、杂技演员 |
| 130..135 | 私货商人、报丧女妖、科学怪人、牙噶巴卜、奥赫、卡扎力 |
| 136..142 | 魔术师、瘟疫医生、炸弹人、鹰身女妖、街头风琴手、维齐尔、事务官 |
| 143..147 | 失忆的镇民、失忆外来者、失忆的爪牙、失忆的恶魔、限 |

- 阵营代码：0 镇民、1 外来者、2 爪牙、3 恶魔、4 传奇、5 奇遇。
- 自定义剧本隐藏未完成的 123/124/126。
- 骑士 122、杂技演员 129 必须可选。
- 143..146 不进入普通角色池。
- 新索引一旦超过 147，必须同步数组长度、扫描上限、全部表格和资源。

## 11. 板子与全员追忆

- 板子 1..13：暗流涌动、黯月初升、梦殒春宵、瓦釜雷鸣、夜半狂欢、罂粟花开、
  自定义剧本、横行霸道、何方教众、风雅集、心理博弈 XI、信口雌黄、全员追忆。
- `BOTC_BoardCount()` 返回 12。
- 全员追忆包含 0..147 中除华灯角色 115/116/117/118/119/121、
  未完成角色 123/124/126 和本板不用的 113 外的全部角色。
- 全员追忆发牌时，玩家只看到对应阵营的失忆占位身份，真实身份只在真值行。
- 真实身份转变后显示新身份；重新发牌时恢复占位。
- 不在场身份面板可发送 3 个身份。

## 12. 角色设计与一句话 DSL

### 12.1 原则

- 自然语言不能直接生成 Galaxy。
- 一句话先转换为 `schema_version=2` 的受约束 JSON。
- DSL 通过校验后才能生成角色接入计划和测试清单。
- 模型不得自行补充时机、目标数量、存活限制、持续时间、胜负条件或隐藏副作用。
- 原句不明确时保留 TODO，并向用户确认，不得猜测。
- 角色草稿完成不等于实现完成；复杂能力必须人工编写并审核。

### 12.2 标准流程

1. 用户提供一句话。
2. 用 `botc.cmd design prompt "..."` 生成严格提示词。
3. 任意大模型只能输出 JSON DSL。
4. 运行 `botc.cmd design validate`。
5. 运行 `botc.cmd design compile` 生成接入计划。
6. 新建 v1 角色规格并实现角色数据。
7. 运行 `role audit`、`check`、`build`。
8. 覆盖正常、失效、边界和换位测试。

### 12.3 必须明确的规则维度

- 时机：准备、被动、首夜、每夜含首夜、次夜起、白天、死亡、处决、提名、投票、换身份。
- 频率：每次、每局一次、每天一次、首次、条件触发。
- 目标：无目标、玩家、角色、玩家 + 角色、阵营、角色类型。
- 目标数量、是否存活、是否允许自己、是否允许重复、是否必须在场。
- 效果：信息、token、死亡、保护、身份变化、登记修改、投票修改、胜利条件、自定义。
- 持续时间：立即、到黎明、到黄昏、当前夜、本局、永久。
- 来源失效：中毒、醉酒、死亡、离场、失去能力时面板和结果分别如何处理。
- 多人持有、能力借用和能力复制时的真身与能力来源。
- token id、名称、短名、作用、放置者、放置时机、移除时机、可见范围、图标和清理条件。
- 相克角色、相克文本、结算顺序、token 变化和告知对象。
- 角色介绍、身份图、夜序图、token 图和资源来源。

### 12.4 夜间顺序分类

- 分类为 `rules` / `role_change` / `interference` / `kill` / `information` / `utility`。
- `rules`：开局设置、全局规则改写。示例：提丰之首、卡扎力、科学怪人、罂粟种植者。
- `role_change`：身份、阵营、认知或能力来源改变。示例：麻脸巫婆、哲学家、舞蛇人、帽匠、理发师。
- `interference`：中毒、保护、限制、强制选择及其他非直接击杀的状态干预。
  示例：投毒者、水手、旅店老板、侍臣、赌徒、僧侣、魔鬼代言人、女巫、洗脑师、驱魔人。
- `kill`：恶魔及直接造成死亡的刀人能力。示例：小恶魔、刺客、教父、造谣者。
- `information`：主要产出身份、人数、阵营或历史信息。示例：占卜师、共情者、守鸦人、送葬者、侍女。
- `utility`：无法归入以上类别但仍参与夜间结算的剩余功能位。
- 粗粒度阶段为 `rules` → `role_change` 与 `interference` 交错段 → `kill` →
  `information` 与 `utility`。官方表不是整齐六段，不得为分类整齐强行重排已实现角色。
- 按实际能力分类，不按阵营分类。爪牙的投毒、保护、限制等能力归入 `interference`；
  只有直接造成死亡的爪牙能力才归入 `kill`。
- 用户没有指定具体夜序时，先选同类现有角色作为 `anchor_role`，再按能力读取和写入依赖插入：
  - 用 `relation=before/after/near` 记录相对位置；不凭空猜具体行号。
  - 只有用户明确给出或已核对最新官方表后才填写 `first` / `other` 的具体行号。
  - 读取身份变化的角色必须排在改变者之后。
  - 提供本夜信息且会被其他角色读取的角色排在读取者之前。
  - Trigger 型能力不塞进普通夜序。
- 首夜与次夜起顺序分别填写；不行动的一侧保留为空。

## 13. 新角色接入清单

- 先确定索引、名称、阵营、阵营倾向、认知颜色、目标类型、行动类型、夜序和首夜规则。
- 接入 `g_roleName`、`g_roleTeam`、`g_roleAlign`、`g_roleTag`。
- 接入 `g_roleTargets`、`g_roleAct`、`g_noAllFirst`、`g_noAllOther`。
- 接入能力总表文本、详情页文本、关键词、身份图、夜序图和相克说明。
- 新 token 同步 `g_tokName`、`g_tokShort`、`g_tokIcon`、`g_tokRole`。
- 新 token 必须覆盖放置、移除、跨日、死亡、换位、第二局和全观察者行清理。
- 每个 token 必须在角色 DSL 中登记 id、名称、短名、作用、放置时机、移除时机、
  可见性、图标和清理条件。
- 专属死亡 token 接入 `g_roleDeathTok`。
- 接入固定板子、自定义池和全员追忆归属。
- 主动能力接入 `BOTC_SkillOpen()`、`BOTC_SkillRender()`、`BOTC_SkillConfirm()`。
- 角色选择接入 `BOTC_PickChoose()` 和 `g_pickSlotRole` 快照。
- 说书人【赋予能力】（`g_pickMode=34`）读取当前板子的角色池；角色在板子上就必须能选到。
- 被动、触发和胜率效果必须走能力层，不得只匹配真实角色索引。
- 完成后检查多面板并发、玩家本地显隐、说书人真值、换说书人、第二局残留。

## 14. 文本规范

- 玩家私聊信息统一为绿色 `【信息】你得知...。`
- 只给规则要求的已知内容，不擅自补充阵营或身份结论。
- 座位写成 `[编号] + 战网名`。
- 并列座位或角色统一用半角英文逗号 `,`，不得混用 `、` 或中文逗号。
- 单角色信息写成 `【信息】你得知<角色>。`
- 公共声称和公开技能使用 `【角色名】X ...`
- 没有角色来源的死亡只用 `【死亡】`。
- `【处决】`和`【复活】`保留各自前缀。
- 技能面板标题只写“选择一名玩家 / 两名玩家 / 三名玩家 / 一个角色”。
- 标题不得出现角色名、括号解释或可据此推断身份的注释。
- 能力总表写简明玩法文本；详情页按「角色能力 / 角色简介 / 规则细节」组织。
- 中文长文本按完整字符断行，禁止按 UTF-8 字节截断。
- 座位名继续使用 `BOTC_NameStr()`，不要手拼颜色和战网名。
- HTML 颜色使用 Galaxy 支持的 `<c val="RRGGBB">...</c>`。

## 15. UI、私聊与网格

- 所有身份网格点击必须通过 `BOTC_PickChoose()` 读取快照 `g_pickSlotRole`。
- 禁止按 UI 槽位号二次硬映射到角色。
- 页码、过滤条件、控件显隐和点击映射按玩家分别保存。
- 其他玩家的魔典或能力表重绘不得覆盖当前网格。
- 【赋予能力】按当前板子显示角色，不得改成无条件全角色池。
  自定义板（板子 7）打开前必须按 `g_csel` 重新同步 `g_boardRole[7]` / `g_boardRoleN[7]`，
  避免自定义板已经包含新角色、赋予窗口却仍读取旧板子缓存。
- 技能专用身份网格默认隐藏底部取消/返回按钮。
- 只有规则明确允许“不得知任何信息”时才保留取消。
- 类别内翻页统一使用同尺寸 `<`、`>`，不显示页码。
- 整页切换和类别翻页不得共用状态。
- 私聊提示使用 `BOTC_PmInfo()`；系统提示使用 `BOTC_Notice()` / `BOTC_SubMsg()`。
- 新增 UI 文件属于资源变更，必须进入 `ui_embed.py` 或基础地图，不能手工塞一次。

## 16. 昼夜、死亡与胜利

- 主链：`BOTC_NightGo()` → `BOTC_DawnResolve()` → `BOTC_DawnReveal()`。
- 白天处决、红叉、token 死亡、复活统一走死亡流程。
- 标记死亡最终经过 `BOTC_DeathBlocker()`。
- 说书人手动红叉使用 `BOTC_MarkDeadPlain()`。
- 夜间死亡默认等天亮统一公开。
- 处决一天一次，处决尸体也占名额。
- 哥布林只有公开声称后、当天死亡类型为处决时才触发胜利。
- 天亮改动必须同时检查僵怖、报丧女妖、月之子、维齐尔、炸弹人的结算顺序。
- 判定存活目标时必须统一排除红叉、死亡 token 和僵怖假死。
- 胜利检查统一走 `BOTC_CheckWin()`。
- 新局清空全部观察者的 token、死人票、提名票、处决名额和复活动画。

## 17. Bank 与统计

- Bank 名 `BOTCSave2` 必须在地图数据中预加载。
- `BankLoad` 玩家参数有效范围是 0..15。
- 不调用不存在的 `BankCreate`。
- 不依赖 `BankLastCreated()` 取有效句柄。
- 场次统计按账号级 `t/g/e/s` 保存，不依赖固定玩家 1。
- 旧 `t1..t13` 首次读取时迁移兼容。
- 统计显示和记录前重新加载并等待。
- 临时低值不得覆盖已缓存的高值。

## 18. 函数导航

- 初始化：`BOTC_Init()`。
- 周期逻辑：`BOTC_Tick_Func()`。
- 点击分发：`BOTC_Click_Func()` / `BOTC_ClickDo()`。
- 聊天分发：`BOTC_Chat_Func()` / `BOTC_ChatDo()`。
- UI 创建：各 `BOTC_Build...()`。
- 座位：`BOTC_PosOf()`、`BOTC_BuildSeatList()`、`BOTC_AfterSeatChange()`。
- 身份能力：`BOTC_SeatTrueRole()`、`BOTC_SetSeatRole()`、`BOTC_HasAbility()`、
  `BOTC_AbilityWorks()`、`BOTC_AbilitySeat()`、`BOTC_AbilityInPlay()`、
  `BOTC_SeatImpaired()`、`BOTC_SourceGoneCleanup()`。
- 角色数据：`BOTC_GrimInitData()`、`BOTC_InitRoleTexts()`、`BOTC_BoardHasRole()`、
  `BOTC_RoleOnBoard()`。
- 板子：`BOTC_BoardOpen()`、`BOTC_BoardRender()`、`BOTC_BoardPick()`、
  `BOTC_BoardFinish()`、`BOTC_BoardSwitch()`。
- 自定义板：`BOTC_CustomOpenSlot()`、`BOTC_CustomSection()`、
  `BOTC_CustomSaveBank()`、`BOTC_CustomLoadBank()`、`BOTC_CustomBankApply()`。
- 私货商人：`BOTC_BootleggerCapture()`、`BOTC_BootleggerEditRefresh()`、
  `BOTC_BootleggerEffectiveText()`、`BOTC_BootleggerSyncText()`、
  `BOTC_BootleggerAnnounce()`。
- 发牌：`BOTC_Deal()`、`BOTC_ConfirmDeal()`、`BOTC_RsOpen()`、`BOTC_RsRender()`、
  `BOTC_RsApply()`、`BOTC_ResetGameVars()`。
- 魔典和技能：`BOTC_GrimRender()`、`BOTC_GrimRelayout()`、`BOTC_PickOpen()`、
  `BOTC_PickChoose()`、`BOTC_PickFilter()`、`BOTC_SkillOpen()`、
  `BOTC_SkillRender()`、`BOTC_SkillConfirm()`、`BOTC_SkillBtnRender()`。
- 声称和 token：`BOTC_DeclareOpen()`、`BOTC_DeclareRender()`、`BOTC_DeclareClick()`、
  `BOTC_TokOpen()`、`BOTC_TokRender()`、`BOTC_TokHidden()`、`BOTC_TokToggleAt()`。
- 私聊：`BOTC_RequestChat()`、`BOTC_RequestJoinSess()`、`BOTC_RequestJoin()`、
  `BOTC_CreateSess()`、`BOTC_JoinSess()`、`BOTC_Leave()`、`BOTC_SessRepair()`。
- 昼夜死亡：`BOTC_NightGo()`、`BOTC_DawnResolve()`、`BOTC_DawnReveal()`、
  `BOTC_DeathToggle()`、`BOTC_MarkDeath*()`、`BOTC_DeathBlocker()`、`BOTC_CheckWin()`。
- 夜间行动：`BOTC_WakeApply()`、`BOTC_WakeToggle()`、`BOTC_AutoWakeNext()`、
  `BOTC_NightOrder*()`、`BOTC_TellerPmTo()`。
- 提名：`BOTC_NomOpen()`、`BOTC_NomClose()`、`BOTC_NomPick()`、`BOTC_NomTally()`、
  `BOTC_PhaseSet()`。
- 存档：`BOTC_BankInit()`、`BOTC_MyBank()`、`BOTC_BankReloadFor()`、
  `BOTC_StatsRecord()`、`BOTC_StatsRender()`。

## 19. 重点防回归清单

- 换座位后不得漏技能目标、每日状态、一次性状态和死亡 token。
- 卡扎力“面板能开但选不了人”优先检查跨换位绑定。
- 模式 3 不得恢复 55..63 原始槽位映射。
- 造谣者、精神病患者的每日限制使用随换位迁移、随新局归零的日期戳。
- 其他角色改身份不得错误清空 `g_philoRole`。
- 魔术师不得在邪恶名单末尾固定追加。
- 维齐尔无能力且无人声称时不得产生投票私聊播报。
- 技能网格不得重新显示底部取消按钮。
- 玩家 + 角色面板不得在选角后直接发动。
- 公聊不得恢复角色来源死亡前缀。
- 骑士和杂技演员不得重新加入自定义剧本隐藏名单。
- 限次角色选否后不得消耗机会。
- `BOTC_NomPick()` 新增循环前先声明局部变量 `i`。
- 新角色索引必须同步全部表、循环、资源、板子和重置逻辑。
- 新角色已加入当前自定义板时，必须同步进入 `g_boardRole[7]` 和【赋予能力】；
  不得出现“板子上有、赋予窗口没有”的板子缓存不同步。
- 第二局不得残留死亡、票、token、面板状态或上一夜技能状态。

## 20. 日志与验收

- `ScriptError.txt`：脚本解析错误和运行期 Galaxy 错误。
- `Alerts.txt`：资源和模型警告。
- `UI.txt`：UI 框架、布局和控件错误。
- `Text.txt`：文本尺寸和字体警告。
- `Graphics.txt`：DirectX 设备重置；历史上可自动恢复，不能单独作为失败依据。
- 检查日志时必须按时间过滤，只分析本次启动之后的新文件。
- 网易账号登录页和“无法运行游戏”不是地图错误；直接启动前必须已有登录态。
- 基础地图的 UI 已经内嵌，不依赖外部 UI 模块。
- 构建成功和脚本无错误不等于界面视觉验收，仍要检查实际画面。

## 21. 开源协作与发布

- 不提交 StormLib 之外来源不明的二进制；第三方依赖必须附版本、许可证和 SHA256。
- 不提交账号、Cookie、Battle.net 缓存、私有依赖或本机绝对凭据。
- 新角色必须附带角色规格、能力文本、测试场景、图标和相克说明。
- 一句话生成结果只能作为草稿，不能绕过人工规则审查。
- 发布前至少运行：
  - `botc.cmd check`
  - `python -m unittest discover -s tools\tests -v`
  - `botc.cmd role audit`
  - `botc.cmd build`
  - `botc.cmd inspect`
- 最终构建文件名和包内地图名分开管理。
- 每次发布记录版本、主要角色变化、已知问题和实测结果。

## 22. 维护方式

- 本文件可超过 150 行，但只保留长期有效的规则。
- 工具入口、正式路径、依赖结构或角色 DSL 改变时必须同步本文件。
- 不写临时任务状态、单次 Bug 过程或可由工具自动检测的细节。
- 历史设计只作参考；当前行为以正式脚本、工具测试和游戏实测为准。
