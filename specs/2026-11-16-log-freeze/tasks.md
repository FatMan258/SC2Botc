# 任务清单：日志 / 复盘 / 全部私聊 长时间卡顿治理

关联：`specs/2026-11-16-log-freeze/spec.md`
唯一代码文件：`scripts/BOTC.galaxy`

## T1 新增全局状态与原型

- [x] 在 `g_logList` 附近新增 `int[14] g_logItems;`
- [x] 新增 `bool g_chatBatch;`
- [x] 在文件前部函数原型区补：
  - `void BOTC_LogItemPush (int p);`
  - `void BOTC_LogItemPop (int p);`
  - `int  BOTC_LogViewCap ();`
- [x] 在 `BOTC_ResetGameVars` 的日志清空处补 `g_logItems[p] = 0;`

完成判据：`check` 无「未声明」报错。

## T2 列表项计数与硬上限

- [x] 在 `BOTC_LogAddLine` 之前实现 `BOTC_LogItemPush` / `BOTC_LogItemPop`
      （上限 1600 项，超出从第 0 项删）
- [x] `BOTC_LogAddLine` 内 5 处 `BOTC_LogItemPush(p)`（AddItem 分支收口后各一次）
- [x] 7 处 `DialogControlRemoveItem(g_logList, PlayerGroupSingle(p), 0)` 替换为 `BOTC_LogItemPop(p)`：
  - `BOTC_PubLogStore`（3 处）
  - `BOTC_VoteLogAdd`（1 处）
  - `BOTC_PmStoreRaw`（3 处）
- [x] `BOTC_LogRender` 与 `BOTC_RpRender` 的 `DialogControlRemoveAllItems` 之后
      各加 `g_logItems[p] = 0;`

完成判据：全文不再有裸的 `DialogControlRemoveItem(g_logList, …, 0)`（仅剩 Push / Pop 内部 2 处）。

## T3 日志分帧加载（不截断，最终方案）

- [x] 撤销日志页签的「只画最近 N 条」截断
- [x] 新增任务数组 `g_logTaskIdx`（每人 3000 槽）与游标 `g_logTaskN/Cur/Ver`、`g_logVer`
- [x] `BOTC_LogRender` 改为 `BOTC_LogTaskStart` + `BOTC_LogTaskStep`：
      模式 0/1/2/3/4 全部原筛选逻辑保留，收集整份索引
- [x] 新增 1/16 秒定时器 `g_tLogTick` / `BOTC_LogTick_Func`，每拍每人补画 160 项
- [x] 分帧期间暂停该玩家页签实时追加（`g_logTaskN[p] == 0` 守卫，共 4 处）
- [x] 4 个日志写入点递增 `g_logVer`；完成后版本变化则重跑一次
- [x] `BOTC_LogClose` 清空任务；`BOTC_ResetGameVars` 重置任务与版本
- [x] 复盘 `BOTC_RpRender` 保留最近 600 条 + 说明行（未选入分帧范围）

完成判据：日志画完是完整历史；每次打开 `AddItem` 不超过 160 项/拍。

## T4 炸弹人批量公告合并聊天渲染

- [x] `BOTC_ChatShow` 末尾改为 `if (!g_chatBatch) { BOTC_ChatRender(p); }`
- [x] `BOTC_BoomKeepConfirm` 首条公告前置 `g_chatBatch = true;`
- [x] 在 `BOTC_PeriodRecord` 之后、13 次 `BOTC_GrimRender` 之前：
      `g_chatBatch = false;` + `for (q = 1; q <= 13; q += 1) { BOTC_ChatRender(q); }`
- [x] 人工核对该区间没有 `return` 提前退出

完成判据：炸弹人一次爆炸的聊天控件写入从约 4000 次降到约 340 次。

## T5 校验与构建

- [x] `tools\botc.cmd check` → OK
- [x] `tools\botc.cmd build` → `work\血染钟楼_build_20261116-013327.SC2Map`（70,505,102 字节）
- [x] `tools\botc.cmd inspect` → 674 成员；依赖虚空之遗 + `bnet:BOTC1/1.0/188805`
- [x] 回读包内 `MapScript.galaxy`，确认存在：
      `BOTC_LogViewCap`、`g_logItems`、`BOTC_LogItemPush`、`BOTC_LogItemPop`、`g_chatBatch`、
      复盘说明行
- [x] 确认全文 `{}` `[]` `()` 配平、无 LF 混入（`check` 通过）

## T6 收尾

- [x] `CHANGELOG.md` 2026-11-16 `### Bug 修复` 追加卡顿治理条目
- [x] 腾讯文档 `DWGpzZEJvanZWWWVD` 增量同步同日条目（version 1001）
- [x] 向用户报告：改动点、构建地图路径、需要人工实测的画面项

## 日志写入 / 读取第二轮优化（2026-11-16）

- [x] 公聊记录 `g_pubLog/g_pubWho/g_pubSeq` 扩到 3600，写满一次丢最旧 1200 行
- [x] 每人私聊记录步长 600→900（`g_pmLog/Who/With/BoxOnly` 共 12600），写满一次丢最旧 300 行
- [x] 投票统计 `g_voteLog` 扩到 900，写满一次丢最旧 300 行
- [x] 全部私聊 `g_allPmLog/Who` 扩到 1500、`g_allPmIn` 扩到 21000，写满一次丢最旧 500 条
- [x] 复盘过程记录 `g_rpLog/g_rpLLog` 扩到 2400，写满一次丢最旧 800 条
- [x] `BOTC_PeriodRecord` 只给在座真人（含保留座位）写私聊
- [x] `BOTC_LogAddLine` 先判断整行是否放得下，放得下就不再算前缀宽度
- [x] 分帧待办容量随公聊扩容到每人 8448 槽（`g_logTaskIdx` 118272）
- [x] 列表项硬上限调整为 20000，保证完整日志与复盘不会被裁剪
- [x] 清空循环上限同步（3600 / 900 / 1500 / 21000 / 2400）
- [x] `check` / `build` / `inspect` / 回读包内脚本全部通过

## 复盘分帧（2026-11-16）

- [x] 新增 `g_logRpStage[14]`、`g_logTaskLast[14]`、`g_rpCollect`、
      `g_rpPmTmp[8192]`、`g_rpPmTmpWho[8192]`、`g_rpPmTmpN`
- [x] `g_logTaskIdx` 扩到 118272（每人 8448 槽）
- [x] 新增 `BOTC_RpCollectProc` / `BOTC_RpCollectPm` / `BOTC_RpStageNext` /
      `BOTC_RpStageRun` / `BOTC_RpTail`
- [x] `BOTC_RpRender` 去掉 600 条截断，改为阶段 1 起画
- [x] `BOTC_LogTaskStep` 增加阶段 1 / 阶段 2 分支，完成后调用 `BOTC_RpStageNext`
- [x] `BOTC_RpPmPut` 增加 `g_rpCollect` 收集分支
- [x] `g_logRealName` / `g_logRealLast` 改为按玩家 `bool[14]`，
      同步 `BOTC_RealPlayerNameText` / `BOTC_RealNameSubstText` / `BOTC_LogNameExtra`
- [x] `BOTC_LogClose` / `BOTC_LogRender` / `BOTC_ClearAllLogs` 复位复盘阶段与标记
- [x] `g_logItems` 硬上限 12000 → 20000
- [x] 移除不再使用的 `BOTC_LogViewCap`
- [x] `check` / `build`（`work\血染钟楼_build_20261116-021147.SC2Map`）/ `inspect` /
      回读包内脚本全部通过
- [x] `CHANGELOG.md` 更新复盘分帧条目

## 人工实测清单（由用户执行）

- [ ] 公聊 1500+ 条后打开【日志】：约 1~2 秒补齐完整历史
- [ ] 说书人【全部私聊】：约 1~2 秒补齐完整记录
- [ ] 【复盘】：分帧补齐完整过程记录 + 白天私聊 + 结束身份，无 600 条截断
- [ ] 一个人看复盘时，另一个人打开普通日志，名字显示正常
- [ ] 炸弹人爆炸后聊天与按钮立即恢复
