# 任务清单：选剧本页面三处 Bug

1. [x] 修改 `scripts/BOTC.galaxy`（共 8 处编辑）
   - 全局变量 `g_startCdHalf`
   - 原型 `void BOTC_StartCdTick ();`
   - 新增 `BOTC_StartCdTick()` 实现（放在 `BOTC_StartCdFunc` 之后）
   - `BOTC_BoardStart()` 加 `g_startCdHalf = 0;`、删除 `TimerStart(g_tStartCd, ...)`
   - `BOTC_StartCdStop()` 加 `g_startCdHalf = 0;`
   - `BOTC_BoardRender()` 加 `BOTC_BsBtnRender();`
   - `BOTC_ClickDo()` 前移 `g_pmVisBtn` 分支、删除原重复分支
   - `BOTC_Tick_Func()` 开头调用 `BOTC_StartCdTick();`
2. [x] LF → CRLF 归一（保持 UTF-8 BOM）
3. [x] `tools\botc.cmd check`（OK）
4. [x] `tools\botc.cmd build`（work\血染钟楼_build_20261117-013828.SC2Map）
5. [x] 回读包内 `MapScript.galaxy` 验证四处关键代码（全部 True）
6. [x] `tools\botc.cmd inspect`
7. [x] `CHANGELOG.md` 追加三条 Bug 修复
8. [x] 腾讯文档 `DWGpzZEJvanZWWWVD` 增量同步（版本 1068→1071）
9. [ ] 用户游戏内人工验收（不自动启动游戏）
