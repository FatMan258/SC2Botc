# 任务清单 · 疯子假能力改为中毒 / 醉酒处理

- [x] T1 `BOTC_SkillWorks` 顶部（`g_liveCorpse` 之后）加 `g_lunFakeAct[q] → false`
- [x] T2 删除 `BOTC_SkillConfirm` 的假能力拦截段
- [x] T3 `BOTC_SkillConfirm` 定义改名 `BOTC_SkillConfirmCore`，上方加原型与同名包装（结算后清 `g_lunFakeAct[p]` + `BOTC_GrimRender`）
- [x] T4 更新 4 处文案 / 注释（WakeApply、SkillOpen、变量注释、假能力设置处）
- [x] T5 归一化 CRLF + UTF-8 BOM，`tools\botc.cmd check` → OK
- [x] T6 `tools\botc.cmd build` 成功，`tools\botc.cmd inspect` 615 成员、`MapScript.galaxy` + `BOTC_CustomLogic.galaxy` 正常
- [x] T7 修订 `CHANGELOG.md`【疯子 × 科学怪人】条目并用 doc-mcp 同步腾讯文档（版本 546 → 548）
