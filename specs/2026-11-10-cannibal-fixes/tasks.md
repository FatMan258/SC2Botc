# 任务清单：食人族（74）互动修复

依据 `spec.md`。顺序执行，每步完成后不要跳过校验。

- [x] T1 新增全局状态与清理
  - `scripts/BOTC.galaxy`：在 `g_cannFedSeat` 声明一带新增 `g_cannOrigAlign` / `g_cannLocked` / `g_cannLun` / `g_cannLunDemon` / `g_cannRestore`。
  - `BOTC_ResetGameVars()` 新局清理循环追加 5 行复位。
  - 头部函数声明区追加 `BOTC_AlignCanChange` / `BOTC_CannLockCheck` 原型。

- [x] T2 杂耍艺人重复唤醒（最小改动，先做）
  - `BOTC_GrantWakeOrder`：在 `if (role == 147) { return 0; }` 后插入 `g_juggUsed` / `!g_juggDone`（含 `BOTC_JugglerDiedAfterGuess()` 例外）两段判断。
  - 先用一次精确 grep 确认 `BOTC_JugglerDiedAfterGuess` 的签名再写。

- [x] T3 教授 / 沙巴洛斯复活补发
  - `BOTC_RestoreOneShot` 尾部加食人族钩子（`g_cannPending = 1; g_cannRestore[q] = true;` + 说书人私聊）。
  - `BOTC_PreGrantStep` 自动补发条件加 `|| g_cannRestore[q]`，并在 `g_cannDoneNight = g_nightNum;` 与 `BOTC_CannPickOpen(q);` 前清标记。

- [x] T4 疯子（38）完整互动
  - `BOTC_AttachGrant` 的 `g_grantRoleBy[q] = role + 1;` 后接 role==38 且 `BOTC_HasAbility(q,74)` 分支：置 `g_cannLun`，复用 `BOTC_CannOpen` 恶魔网格。
  - `BOTC_CannPick` 选中后记录 `g_cannLunDemon[g_cannSeat]`。
  - `BOTC_IsLunatic` 增加 `g_cannLun[q]`；`BOTC_RealLunaticSeat` / `BOTC_LunaticActingSeat` 的“假装那个”条件加 `|| g_cannLun[i]`。
  - `BOTC_LunaticPickNotify` 开头加食人族分支（私聊说书人 + `BOTC_PmInfoDemons` 告知身份与目标，不产生死亡，提前 return）。
  - 确认角色 38 的技能确认分支会调用 `BOTC_LunaticPickNotify`；缺失则补调用。

- [x] T5 异教领袖 / 莽夫阵营锁定
  - `BOTC_GoonTouch`：改阵营前记录原阵营；已锁定时把目标阵营改回当前并私聊说书人。
  - `BOTC_CultChoiceAnswer`：同样记录 + 拦截。
  - 新增 `BOTC_AlignCanChange` / `BOTC_CannLockCheck` 实现；`BOTC_CannExecHooks` 末尾调用。

- [x] T6 校验
  - `tools\botc.cmd check`
  - `tools\botc.cmd build`
  - `tools\botc.cmd inspect`（脚本首尾标记、`InitCustomScript` / `InitMap`、依赖 `bnet:BOTC1/1.0/188805`、内嵌 UI）
  - 全文括号配平与新增函数行号范围核对；不启动游戏。

- [x] T7 收尾
  - `CHANGELOG.md` 追加当日“角色与机制”四条。
  - doc-mcp `find_and_replace` / `insert_paragraph_with_text` 增量同步腾讯文档「星际血染钟楼更新日志」（file_id `DWGpzZEJvanZWWWVD`）。
