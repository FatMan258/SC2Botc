# 选剧本页面三处 Bug 修复规格

状态：待批准
日期：2026-11-17
涉及文件：`scripts/BOTC.galaxy`、`CHANGELOG.md`、腾讯文档「星际血染钟楼更新日志」

## 1. 问题

用户反馈（首次进图、玩家 1 为真人、点剧本后有绿 √）：

1. 【切换板子】【添加传奇角色】两个按钮出现在选剧本页面。
2. 选中剧本后点【开始说书】，10 秒倒计时数字不变化。
3. 点击【私聊可见性】按钮没有任何反应。

已确认前提：`g_boardOpen` 为真、`g_boardSel` 有效（有绿 √），所以不是「没选剧本」分支。

## 2. 根因

### 2.1 顶部两按钮残留在选板页

- `BOTC_BsBtnRender()`（`scripts/BOTC.galaxy:72055`）的职责是先隐藏
  `g_bsBtnDlg` / `g_tsBtnDlg` / `g_legBtnDlg`，并在 `g_started || g_boardOpen` 时直接 `return`
  不再显示；只有不在剧本里时才给说书人显示这三个按钮。
- `BOTC_BoardOpen()` 末尾调用了它，但 `BOTC_BoardRender()` 没有调用。
- 任何「重绘选板页但没有重跑 `BOTC_BoardOpen()`」的路径（翻页、返回选板页、换局后刷新），
  只要此前顶部按钮处于可见状态，就会把按钮留在选剧本页上。

### 2.2 倒计时定格

- `BOTC_BoardStart()` 置 `g_boardStarting = true; g_startCdSec = 10; g_startCdOn = true;`，
  最后 `TimerStart(g_tStartCd, 1.0, true, c_timeGame)`。
- 唯一推进数字的是计时器触发的 `BOTC_StartCdFunc()`
  （`scripts/BOTC.galaxy:71774`），它每次把 `g_startCdSec` 减 1。
- 该触发不生效时：数字停在 10，`BOTC_StartCdFunc` 里的 `BOTC_BoardStartGo()` 永不执行，
  `g_boardStarting` 永远为真 —— 界面看起来就是「点了开始说书，倒计时不走」。

### 2.3 私聊可见性无响应

- 点击分发 `scripts/BOTC.galaxy:11018-11039`：`if (g_boardOpen)` 内先判断
  `if (g_boardStarting) { ... return true; }`，只认开始按钮与剧本按钮，其余点击全部吞掉。
- `g_pmVisBtn` 的处理位于该分支之后（`scripts/BOTC.galaxy:11059-11064`），
  因此倒计时卡住（`g_boardStarting` 恒真）时，【私聊可见性】永远点不到。

## 3. 修改方案（仅改 `scripts/BOTC.galaxy`）

### 3.1 倒计时改为 tick 驱动（不依赖 TimerStart）

1. 全局变量区（`g_startCdSec` 声明之后，约 1928 行）新增：
   ```galaxy
   int         g_startCdHalf;      // 倒计时半秒累加（0/1；2 拍 = 1 秒）
   ```
2. 前置原型区（`BOTC_StartCdStop` 原型附近，约 3577 行）新增：
   ```galaxy
   void   BOTC_StartCdTick ();
   ```
3. 在 `BOTC_StartCdFunc()` 之后新增实现：
   ```galaxy
   // 【选板倒计时改由 0.5 秒 tick 推进】（用户 2026-11-17）：原来只靠
   //   TimerStart(g_tStartCd) 的周期触发每秒减 1，该触发不生效时数字会定格在 10，
   //   且 g_boardStarting 永远为真。现在由 tick 累加半秒，2 拍减 1 秒。
   void BOTC_StartCdTick () {
       if (!g_boardOpen || !g_boardStarting || !g_startCdOn) {
           return;
       }
       g_startCdHalf = g_startCdHalf + 1;
       if (g_startCdHalf < 2) {
           return;
       }
       g_startCdHalf = 0;
       g_startCdSec = g_startCdSec - 1;
       if (g_startCdSec <= 0) {
           BOTC_StartCdStop();
           BOTC_BoardStartGo();
           return;
       }
       BOTC_BoardStartCdRender();
   }
   ```
4. `BOTC_BoardStart()`：
   - `g_startCdSec = 10;` 之后补一行 `g_startCdHalf = 0;`
   - 删除 `TimerStart(g_tStartCd, 1.0, true, c_timeGame);`，改为注释说明倒计时由
     `BOTC_StartCdTick()` 在 tick 里推进。
5. `BOTC_StartCdStop()`：补 `g_startCdHalf = 0;`。
6. `BOTC_Tick_Func()` 函数体最开始插入 `BOTC_StartCdTick();`（必须早于该函数内任何
   提前 `return`，保证 0.5 秒 tick 每次都调用）。
7. `BOTC_StartCdFunc()` 保持原样（计时器不再启动，实际不会触发；保留 `g_startPending`
   分支不影响现有流程）。

### 3.2 选板页每次都收起顶部按钮

`BOTC_BoardRender()` 局部变量声明之后、`BOTC_BuildSeatList();` 之前插入一行：
```galaxy
BOTC_BsBtnRender();
```
此时 `g_boardOpen` 已为真，`BOTC_BsBtnRender()` 会隐藏三个按钮并收掉传奇面板，
不会反向显示。

### 3.3 私聊可见性优先响应

`BOTC_ClickDo()` 的 `if (g_boardOpen) {` 块内，把 `g_pmVisBtn` 判断提到
`if (g_boardStarting)` 之前：
```galaxy
if (g_boardOpen) {
    // 【私聊可见性开关优先响应】（用户 2026-11-17）：倒计时卡住时也必须能点
    if (p == g_teller && c == g_pmVisBtn) {
        BOTC_PmVisToggle();
        return true;
    }
    if (g_boardStarting) {
        ...
```
同时删除原 11059-11064 行的重复 `g_pmVisBtn` 分支（只保留一处，避免双份逻辑）。

## 4. 不做的事

- 不调整 `BOTC_BoardStart` 的 `g_boardFade < 4` 门槛。
- 不改 `g_boardStarting` 期间禁止改剧本的提示逻辑。
- 不动日志、私聊、角色能力相关代码。
- 不新增 / 删除 UI 控件与资源。

## 5. 验证

1. 用 Python 二进制把 `scripts/BOTC.galaxy` 的 LF 统一回 CRLF（保留 UTF-8 BOM）。
2. `tools\botc.cmd check` 通过（无单独 LF、无语法错误）。
3. `tools\botc.cmd build` 生成新地图。
4. 用 `stormlib_mpq.MPQArchive` 回读包内 `MapScript.galaxy`，确认：
   - 含 `BOTC_StartCdTick`；
   - `BOTC_BoardRender` 内有 `BOTC_BsBtnRender();`；
   - `g_pmVisBtn` 分支位于 `if (g_boardStarting)` 之前；
   - `BOTC_BoardStart` 内不再有 `TimerStart(g_tStartCd`；
   - `InitCustomScript` / `InitMap` 完整。
5. `tools\botc.cmd inspect` 正常。
6. 游戏内人工验收（由用户执行，本规格不自动拉起星际 II）：
   - 进图选剧本页看不到【切换板子】【添加传奇角色】；
   - 点【开始说书】后数字 10→9→…→1，走完进入取名阶段；
   - 倒计时期间点【私聊可见性】能切换并提示。

## 6. 收尾

- `CHANGELOG.md` 当日「Bug 修复」下追加三条（顶部按钮残留 / 倒计时定格 / 私聊可见性无响应）。
- 腾讯文档「星际血染钟楼更新日志」（`DWGpzZEJvanZWWWVD`）用 `find_and_replace` /
  `insert_paragraph_with_text` 增量同步这三条，不整篇覆盖。
