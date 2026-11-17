# 日志系统：打不开日志 + 局中按钮/聊天失效（跟进）

日期：2026-11-17
状态：待批准（批准前不修改 `scripts/BOTC.galaxy`）

## 1. 背景与结论

用户反馈两个现象：

1. 局内**部分**玩家打不开日志；
2. 对局中途**所有按钮和聊天**失效（时停）。

上一轮（`specs/2026-11-16-log-freeze`）已把日志/复盘/全部私聊从「一次灌入几千项」改成分帧
加载，但那一轮的驱动定时器签名写错，导致本轮的根因问题。经静态核对，根因与修复如下。

## 2. 根因（已定位）

### R1 时停根因：1/16 秒定时器签名错误 → 定时器从未触发

`BOTC_LogTick_Func` 之前声明 / 实现为 `void BOTC_LogTick_Func()`，但 `TriggerCreate` 只认
`bool (bool testConds, bool runActions)` 这一种触发器签名。签名不匹配 → 该定时器实际上从不
运行，两个直接后果：

- `g_sayCool[i]`（公聊/私聊切换冷却，每拍应递减）永远停在 4，点一次切换之后就再也切不动，
  表现为「聊天失效」。
- 日志分帧的延迟收集（`g_logTaskN[p] = -1` 标记）永远没人处理，日志列表永远补不出来。

已确认三处已全部改为正确签名（当前工作区已改，未提交）：

- 前部原型 L2454：`bool BOTC_LogTick_Func (bool testConds, bool runActions);`
- 函数体 L6828：`bool BOTC_LogTick_Func (bool testConds, bool runActions) {`
- 定时器创建 L95046-95049：`TimerCreate` / `TriggerCreate("BOTC_LogTick_Func")` /
  `TriggerAddEventTimer` / `TimerStart(g_tLogTick, 0.0625, true, c_timeGame)`。

### R2 部分玩家打不开日志：每拍固定从 1 号开始，后段玩家饿死

分帧驱动每拍总预算 320 项、每人一批 80 项。旧循环每拍都从玩家 1 开始，1..4 号把 320 项
预算吃光，5 号以后开着大日志的一直轮不上，表现为「部分玩家打不开日志」。

已改为公平轮转（当前工作区已改，未提交）：`g_logTurn` 记录轮转起点，13 拍内每人都轮到，
修复后段玩家饿死。

## 3. 本轮剩余改动（两个小修正）

改动文件：`scripts/BOTC.galaxy`（唯一代码文件）。

### F1 修 `BOTC_LogTaskRestart` 污染全局 `g_logBatch`（L6820）

现状：

```galaxy
void BOTC_LogTaskRestart (int p) {
    DialogControlRemoveAllItems(g_logList, PlayerGroupSingle(p));
    g_logItems[p] = 0;
    BOTC_LogTaskStart(p);
    g_logBatch = 160;
    BOTC_LogTaskStep(p);
}
```

问题：`g_logBatch` 是全局，外层 `BOTC_LogTick_Func` 用它记账
（`g_logBatch = 80; ... left = left - g_logBatch;`）。`BOTC_LogTaskRestart` 在
`BOTC_LogTaskStep`（L6811）里被调用，把 `g_logBatch` 改成 160 后，外层那一拍会把 160 当
80 记账，且这次 restart 会一次画到 160 项，破坏预算与公平轮转。

修复：删除 `g_logBatch = 160;` 这一行。`BOTC_LogTaskRestart` 只会被 `BOTC_LogTaskStep`
（L6811）调用，而后者由 `BOTC_LogTick_Func` 在设置好 `g_logBatch = 80`（或 `min(80,left)`）
之后调用，因此删掉后 `BOTC_LogTaskStep` 使用外层已设好的预算值，行为正确。

### F2 修 `BOTC_LogTaskStep` 私聊负索引缺边界检查（L6785-6788）

现状：

```galaxy
else if (v < 0) {
    i = (-v) - 1;
    BOTC_LogAddLine(p, g_pmLog[(p * 900) + i], g_pmWho[(p * 900) + i]);
}
```

同函数阶段 2 的两个分支（L6774、L6780）都有 `i >= 0 && i < 计数` 边界检查，唯独这个
私聊负索引分支没查。分帧期间若该玩家私聊数组发生批量回卷（写满 900 左移 300），已收集的
负索引 `i` 可能指向回卷后的旧位置，读到脏数据（数组 900 内不越界崩溃，但内容错乱；
版本号 `g_logVerPm` 会触发重跑自愈，边界检查是防御性一致化）。

修复：

```galaxy
else if (v < 0) {
    i = (-v) - 1;
    if (i >= 0 && i < g_pmLogCount[p]) {
        BOTC_LogAddLine(p, g_pmLog[(p * 900) + i], g_pmWho[(p * 900) + i]);
    }
}
```

## 4. 验收标准

1. `tools\botc.cmd check` 通过（CRLF / BOM 不变）。
2. `tools\botc.cmd build` 成功；`tools\botc.cmd inspect <地图>` 依赖仍为
   虚空之遗 + `bnet:BOTC1/1.0/188805`。
3. 回读包内 `MapScript.galaxy`，确认：
   - `BOTC_LogTick_Func` 为 `bool (bool, bool)` 签名；
   - `BOTC_LogTaskRestart` 内不再有 `g_logBatch = 160;`；
   - `BOTC_LogTaskStep` 的 `v < 0` 分支带 `i < g_pmLogCount[p]` 检查。
4. 人工实测（用户执行）：
   - 多人同时打开日志，5 号以后玩家也能在 1~2 秒内补齐日志；
   - 打开日志后公聊/私聊切换（Tab）能连续切换，不再卡死；
   - 打开日志期间再切页签 / 换筛选，列表最终完整且顺序正确。

## 5. 风险与回滚

- 改动仅限 `BOTC_LogTaskRestart` 删一行、`BOTC_LogTaskStep` 加一个 `if`，不触碰任何
  数组容量、日志文本、角色结算。回滚即按两处反向还原。

## 6. 收尾

- `CHANGELOG.md` 2026-11-17 `### Bug 修复` 追加一条。
- 腾讯文档「星际血染钟楼更新日志」（`DWGpzZEJvanZWWWVD`）增量同步同日条目。
