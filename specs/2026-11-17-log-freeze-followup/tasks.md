# 任务清单：日志打不开 + 局中按钮/聊天失效（跟进）

关联：`specs/2026-11-17-log-freeze-followup/spec.md`
唯一代码文件：`scripts/BOTC.galaxy`

## T1 修 `BOTC_LogTaskRestart` 预算污染

- [x] 删除 `BOTC_LogTaskRestart` 内 `g_logBatch = 160;` 一行（L6820）
- [x] 核对删除后函数仍为：清空 → `BOTC_LogTaskStart(p)` → `BOTC_LogTaskStep(p)`

完成判据：`grep g_logBatch` 只剩声明、L6601、L6763、L6869/6870/6871/6874，不再有 6820。

## T2 修 `BOTC_LogTaskStep` 私聊负索引边界检查

- [x] 在 `v < 0` 分支给 `BOTC_LogAddLine` 加 `if (i >= 0 && i < g_pmLogCount[p])` 保护

完成判据：该分支与阶段 2 两个分支（L6774 / L6780）边界检查风格一致。

## T3 校验与构建

- [x] `tools\botc.cmd check` → OK
- [x] `tools\botc.cmd build` → 产出新地图
- [x] `tools\botc.cmd inspect <地图>` → 依赖虚空之遗 + `bnet:BOTC1/1.0/188805`
- [x] 回读包内 `MapScript.galaxy` 确认三处（签名 / 删行 / 边界检查）

## T4 收尾

- [x] `CHANGELOG.md` 2026-11-17 `### Bug 修复` 追加条目
- [x] 腾讯文档 `DWGpzZEJvanZWWWVD` 增量同步同日条目
- [x] 向用户报告改动点、构建地图路径、需人工实测的画面项
