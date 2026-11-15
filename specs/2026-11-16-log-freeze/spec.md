# 日志 / 复盘 / 全部私聊 长时间卡顿治理

日期：2026-11-16
状态：待批准（批准前不修改 `scripts/BOTC.galaxy`）

## 1. 背景与已确认结论

玩家反馈：炸弹人（138）引爆后「全场时停」——聊天按回车无反应、所有按钮无响应。

前两轮已做（保留不回退）：

- 哲学家醉酒判定重入保护（`BOTC_PhiloDrunkSeat` 包装 `BOTC_PhiloDrunkSeatCore`），修复
  `BOTC_SeatDead → BOTC_LivingCorpseCountsAlive → BOTC_AbilityWorks → BOTC_SeatImpaired →
  BOTC_SeatIsDrunk → BOTC_PhiloDrunkSeat` 的无限递归。
- 炸弹人爆炸逐座位写时段记录合并为 1 条（`BOTC_BoomKeepConfirm`）。

本轮方向修正：**不是脚本崩溃，而是单帧内同步工作量过大**。Galaxy 的全部触发器跑在同一线程，
某一次点击/公告里如果连续做几千次控件写入与数组搬移，期间聊天触发器和按钮点击都得不到处理，
表现出来就是「整局时停」。已从代码确认以下放大点（全部有行号证据，行号为读取时位置）：

### 1.1 打开日志 / 切页签 / 打开复盘：一次性灌入数千个列表项

- `BOTC_LogRender`（L6400-6527）：
  - 模式 0 公聊：`for (i = 0; i < g_pubLogCount; i += 1)`，`g_pubLog` 上限 **2400**；
  - 模式 3 系统消息：公聊最多 2400 + 私聊最多 600；
  - 模式 1 私聊：最多 600；模式 2 投票：最多 600；
  - 模式 4【全部私聊】：`for (i = 0; i < g_allPmCount; i += 1)`，上限 **1000**（L6436）。
- `BOTC_RpRender`（L6307-6398）：过程记录最多 **1600** 条 + 白天私聊备份最多 **1000** 条。
- 每条都走 `BOTC_LogAddLine`（L7719-7789），单行成本：
  - `BOTC_LogNameExtra`：整行逐单元扫描（L7669）；
  - `BOTC_PrefixEnd`：13 次 `BOTC_SayToken` 字符串比较（L7819-7840）；
  - `BOTC_TextWidth(s)`：整行逐单元扫描（L7647-7662），必要时再看前缀宽度；
  - 超宽时 `BOTC_WrapCut`（L7871-7929）再逐单元扫描，且每轮都 `StringSub` 复制子串；
  - 最后 `DialogControlAddItem`，长行会拆成 2~3 项。
- 触发点：`BOTC_LogOpen`（L6718）、`BOTC_LogSetMode`（L6755）、`BOTC_LogPickTake`（L6691）、
  `BOTC_PmDropPrefix`（L6571-6573）、换页签。
- 结论：打开【日志】/【全部私聊】/【复盘】的那一拍是数千次全行扫描 + 数千次 `AddItem`，
  单帧耗时可达秒级 → 表现为时停。

### 1.2 日志列表项无上限、回卷只删 1 项 → 列表长期膨胀

- 数组满时回卷只删一个列表项：
  `BOTC_PubLogStore` L5588 / L5600 / L5607，`BOTC_PmStoreRaw` L5753 / L5765 / L5775，
  `BOTC_VoteLogAdd` L5681，`BOTC_AllPmStoreTo` 实时追加路径 L5908。
- 但新增一条记录可能产生 2~3 个列表项（换行续行、缩进续行），所以每轮回卷净增项，
  还会留下「孤儿续行」。列表越大，后续每次 `AddItem` / `RemoveItem` / 滚动越慢，
  越到后期越卡。

### 1.3 炸弹人爆点：单帧批量放大

`BOTC_BoomKeepConfirm`（L41479-41555）每个死亡座位执行
`BOTC_MarkDeathRowTok` + `BOTC_DeclareRender()` + `BOTC_PubAnnounce` + `BOTC_PmStore(teller, …)`：

- `BOTC_PubAnnounce`（L5472-5476）= `BOTC_ChatShowAll`（13 人 × 26 行 = **338 次
  `SetDialogItemText`**，每行还经 `BOTC_LineText` / 名字替换）+ `BOTC_PubLogStore`
  （满 2400 时整段左移 2400×3 ≈ 7200 次赋值）+ 字幕。
- `BOTC_PmStore` 满 600 时左移 599×4 ≈ 2396 次赋值 + `BOTC_PmBoxRender` 14 行。
- 11 人死亡 ≈ 12 条公告 + 11 条私聊 + 1 条时段记录 → 4000+ 次 UI 文本写入、
  约 10 万次数组搬移；末尾还有 13 次 `BOTC_GrimRender`。
- `BOTC_PeriodRecord`（L5648-5658）单条放大：13 次 `BOTC_PmStore` +
  `BOTC_AllPmStore`（满 1000 时 999×14 ≈ 1.4 万次赋值）+ `BOTC_PubLogStore` +
  `BOTC_VoteLogAdd` + `BOTC_RpAdd`。

### 1.4 全部私聊满 1000 后每条私聊的固定成本

`BOTC_AllPmStoreTo`（L5858-5884）满 1000 时整段左移 999 行 × 13 列 bool ≈ 1.4 万次写入，
并复制 999 条字符串。单条不致命，但叠加 1.2 的列表追加会放大。

## 2. 本轮范围（只改性能，不改规则与文案）

改动文件：`scripts/BOTC.galaxy`（唯一代码文件）。

不做的事：

- 不改任何角色能力结算、不改日志文本、不改数组容量、不改日志页签语义。
- 不引入环形缓冲（`BOTC_PubLogStore` / `BOTC_PmStoreRaw` / `BOTC_AllPmStoreTo` / `BOTC_RpAdd`
  的整段左移保持原样）。环形缓冲需要改全部读取点，风险高，记为后续可选优化。

## 3. 设计与实现决定

### D1 日志 / 复盘只画「最近 N 条」，数组仍全量保留

新增常量入口（放在 `BOTC_ChatWrapWidthLog` 附近）：

```galaxy
// 【日志渲染上限】只画最近 N 条，避免一次灌入几千个列表项卡住整帧。
//   存档数组本身不裁剪，复盘 / 全部私聊的数据不丢。
int BOTC_LogViewCap () { return 400; }
```

修改 `BOTC_LogRender`：

1. 局部变量区补 `int start;`（必须在该函数第一条语句之前）。
2. 模式 4【全部私聊】：把
   `for (i = 0; i < g_allPmCount; i += 1)` 改为
   ```galaxy
   start = g_allPmCount - BOTC_LogViewCap();
   if (start < 0) { start = 0; }
   for (i = start; i < g_allPmCount; i += 1)
   ```
   过滤逻辑（`g_logViewWho` / `BOTC_IsPeriodMark` / `g_allPmIn`）不变。
3. 模式 0 公聊与模式 3 的公聊段：`g_pubLogCount` 同理只取尾部 `BOTC_LogViewCap()` 条。
4. 模式 3 的私聊段、模式 1 私聊段：`g_pmLogCount[p]` 同理只取尾部。
5. 模式 2 投票：`g_voteLogCount` 取尾部（同一上限）。

修改 `BOTC_RpRender`：

1. 局部变量区补 `int start;`。
2. 过程记录段（现在 `for (i = 0; i < n; i += 1)`）改为只画最近
   `BOTC_LogViewCap() + 200`（= 600）条，并在该段前加一行
   `---- 仅显示最近 600 条过程记录（完整记录仍在存档中）----` 的说明行，
   让说书人知道上方不是全部。
3. 白天私聊备份段（`g_rpLPm`）同理只画最近 400 条。

### D2 列表项数硬上限 + 计数同步

1. 全局变量区新增（放在 `g_logList` 附近）：
   ```galaxy
   int[14] g_logItems;   // 每人日志列表当前项数：防止回卷只删 1 项导致列表无限膨胀
   ```
2. 新增两个函数（`BOTC_LogAddLine` 之前）：
   ```galaxy
   void BOTC_LogItemPush (int p) {
       if (p < 1 || p > 13) { return; }
       g_logItems[p] = g_logItems[p] + 1;
       while (g_logItems[p] > 1600) {
           DialogControlRemoveItem(g_logList, PlayerGroupSingle(p), 0);
           g_logItems[p] = g_logItems[p] - 1;
       }
   }

   void BOTC_LogItemPop (int p) {
       if (p < 1 || p > 13) { return; }
       if (g_logItems[p] <= 0) { return; }
       DialogControlRemoveItem(g_logList, PlayerGroupSingle(p), 0);
       g_logItems[p] = g_logItems[p] - 1;
   }
   ```
   需要在该文件前部原型区补两个原型。
3. `BOTC_LogAddLine` 里 7 处 `DialogControlAddItem(g_logList, PlayerGroupSingle(p), …)`
   全部改成先 AddItem 再 `BOTC_LogItemPush(p);`（不要改变参数）。
4. 7 处 `DialogControlRemoveItem(g_logList, PlayerGroupSingle(p), 0);`
   （L5588 / L5600 / L5607 / L5681 / L5753 / L5765 / L5775）替换为 `BOTC_LogItemPop(p);`。
5. `BOTC_LogRender` 与 `BOTC_RpRender` 开头 `DialogControlRemoveAllItems(...)` 之后
   各加 `g_logItems[p] = 0;`。
6. 新局重置（`BOTC_ResetGameVars` 里日志清空附近）加 `g_logItems[i] = 0;`（循环 1..13）。

### D3 批量公告只渲染一次聊天窗（炸弹人）

1. 全局变量区新增：`bool g_chatBatch;`
2. `BOTC_ChatShow` 末尾 `BOTC_ChatRender(p);` 改为
   ```galaxy
   if (!g_chatBatch) {
       BOTC_ChatRender(p);
   }
   ```
3. `BOTC_BoomKeepConfirm`：
   - 在 `BOTC_PubAnnounce("炸弹人引爆，除保留者外的玩家死亡。");` 之前置 `g_chatBatch = true;`
   - 在 `BOTC_PeriodRecord(...)` 之后、`for (q = 1; q <= 13; q += 1) { BOTC_GrimRender(q); }`
     之前执行：
     ```galaxy
     g_chatBatch = false;
     for (q = 1; q <= 13; q += 1) {
         BOTC_ChatRender(q);
     }
     ```
   - 该区间没有 `return`，不存在 `g_chatBatch` 卡在 true 的路径。
   - `BOTC_ChatRender` 只画最近 26 行，批量结束后画一次与逐条画结果一致。

### D4 不做的部分（明确记录）

- `BOTC_PeriodRecord` 仍对 13 人各写一次私聊（离线座位也写），不改。
- `BOTC_ChatShowAll` 单条公告仍是 13×26 次写入，不改（单条可接受）。
- 数组回卷整体左移不改。

## 4. 验收标准

1. `tools\botc.cmd check` 通过（CRLF / BOM 不变）。
2. `tools\botc.cmd build` 成功，`tools\botc.cmd inspect <地图>` 显示依赖仍为
   虚空之遗 + `bnet:BOTC1/1.0/188805`。
3. 从构建包回读 `MapScript.galaxy`，确认存在：`BOTC_LogViewCap`、`g_logItems`、
   `BOTC_LogItemPush`、`BOTC_LogItemPop`、`g_chatBatch`，且炸弹人批量渲染顺序正确。
4. 人工实测（用户执行）：
   - 公聊累积 1500+ 条后打开【日志 → 公聊记录】：打开应立即出现（不再数秒白屏）。
   - 说书人打开【全部私聊】：立即出现最近 400 条，可滚动。
   - 结算后打开【复盘】：立即出现，末尾有「仅显示最近 600 条过程记录」说明。
   - 炸弹人引爆：公告仍逐条出现在聊天窗与日志，按钮与聊天在爆炸结算结束后立即可用。
5. 行为不回退：日志「看某玩家」筛选、屏蔽过滤、时段分隔标记、复盘身份快照均保持原样。

## 5. 风险与回滚

- 风险：日志界面不再显示最早的历史（数据仍在数组与复盘中）。若用户需要全量回看，
  后续可加「加载更早」按钮分帧追加，不在本轮。
- 风险：`g_logItems` 计数与实际项数不一致会把老内容提前删掉。所有 AddItem / RemoveItem
  点都已统一走 Push / Pop，且两处 `RemoveAllItems` 都清零，可避免漂移。
- 回滚：只涉及上述函数与两个全局变量，按改动点反向还原即可，不影响其它模块。

## 6. 收尾

- `CHANGELOG.md` 的 2026-11-16 `### Bug 修复` 追加一条（卡顿治理）。
- 腾讯文档「星际血染钟楼更新日志」（`DWGpzZEJvanZWWWVD`）增量同步同日条目。

## 7. 最终实现（2026-11-16 修订，替代 D1）

用户要求「日志必须看完整」，因此**撤销日志页签的截断显示**，改为分帧加载：

- 新增 `int[42000] g_logTaskIdx`（每人 3000 槽）、`g_logTaskN` / `g_logTaskCur` /
  `g_logTaskVer` / `g_logVer`。
- `BOTC_LogRender` 不再直接循环画行，改为 `BOTC_LogTaskStart(p)` 收集整份筛选后的索引，
  再 `BOTC_LogTaskStep(p)` 画第一批。
- 新增 1/16 秒定时器 `g_tLogTick` → `BOTC_LogTick_Func()`，每拍给每个有任务的玩家补画
  160 项，约 1~2 秒补齐；日志内容不截断。
- 分帧期间暂停该玩家页签的实时追加（`g_logTaskN[p] == 0` 守卫）；若期间有新日志
  （`g_logVer` 变化），完成后自动重跑一次，保证顺序与完整性。
- 关闭日志时清空任务。
- 复盘（`BOTC_RpRender`）也改成分帧加载，见第 8 节（本轮已覆盖，不再只画最近 600 条）。
- 额外的 `g_logItems` 20000 项硬上限保留，仅作列表项膨胀兜底。

## 8. 复盘分帧（2026-11-16，替代「复盘只画最近 600 条」）

用户要求复盘同样完整且不卡，做法与日志页签一致：

- `BOTC_RpRender` 只同步画「① 开局真实身份」和「---- 过程记录 ----」标题，
  随后把过程记录收集成待办（`BOTC_RpCollectProc`），由 1/16 秒定时器补画。
- 阶段状态 `g_logRpStage[14]`：1 = 过程记录，2 = 白天私聊，0 = 非复盘。
  `BOTC_RpStageNext` 在上一阶段画完后推进；`BOTC_RpStageRun` 负责起画，
  阶段为空时直接跳过，避免空阶段卡住（`BOTC_LogTaskStep` 对 0 项任务会直接返回）。
- 白天私聊：看上一局时直接读备份 `g_rpLPm`（负数编码）；看本局时先用
  `BOTC_RpCollectPm` 借 `BOTC_RpDayPm` 把各座位白天段收进临时数组
  `g_rpPmTmp` / `g_rpPmTmpWho`（`g_rpCollect` 期间 `BOTC_RpPmPut` 只写临时数组），
  再按正数编码分帧输出。
- 收尾 `BOTC_RpTail` 画「---- 结束真实身份 ----」与全部座位身份行。
- 待办槽位每人 8448（`g_logTaskIdx` 118272），覆盖 2400 条过程记录 + 8192 行白天私聊。
- 复盘名字标记改为**按玩家** `bool[14] g_logRealName` / `g_logRealLast`，
  多拍期间不会把其他玩家的日志名字一起改成星际名；关面板、切回普通页签、
  清空日志时都会复位阶段与标记。
- 实时追加守卫按玩家生效：分帧期间新增日志不会插进列表中间，画完后普通页签会重跑一次。

