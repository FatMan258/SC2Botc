# 验收清单：食人族（74）互动修复

- [x] 新增全局状态 `g_cannOrigAlign` / `g_cannLocked` / `g_cannLun` / `g_cannLunDemon` / `g_cannRestore` 已在文件头部声明，并在 `BOTC_ResetGameVars()` 的新局清理中复位（第 15575-15577 行一带）。
- [x] `BOTC_AlignCanChange` / `BOTC_CannLockCheck` 既有前置原型（第 2435-2436 行）也有实现（第 59602 / 59611 行）。
- [x] 杂耍艺人（58）经附加能力获得时不会重复唤醒：`BOTC_GrantWakeOrder` 在 `role == 147` 之后加了 `g_juggUsed` 与 `!g_juggDone && !BOTC_JugglerDiedAfterGuess()` 两道闸（第 47785 行）。
- [x] 教授 / 沙巴洛斯复活补发：`BOTC_RestoreOneShot` 在食人族持有时置 `g_cannPending` / `g_cannRestore`（第 47958 行），`BOTC_PreGrantStep` 按 `|| g_cannRestore[q]` 放宽补发条件并在成功后清标记。
- [x] 疯子（38）完整互动：`BOTC_AttachGrant` 获能即开恶魔网格（第 28786 行），`BOTC_CannPick` 记录认知恶魔（第 59720-59721 行），`BOTC_IsLunatic` 认 `g_cannLun`（第 44788 行），`BOTC_RealLunaticSeat` / `BOTC_LunaticActingSeat` 认 `g_cannLun[i]`（第 44811 / 44853 行），`BOTC_SkillConfirm` 向恶魔播报身份与目标（第 56874 行），`BOTC_CannRevert` 清除认知状态（第 59680 行）。
- [x] 异教领袖 / 莽夫阵营锁定：`BOTC_GoonTouch` 与 `BOTC_CultChoiceAnswer` 先记原阵营、已锁定时拒绝改阵营并私聊说书人；`BOTC_CannExecHooks` 末尾调用 `BOTC_CannLockCheck(q)`（第 59596 行）。
- [x] `tools\botc.cmd check` 通过（OK）。
- [x] `tools\botc.cmd build` 通过，产出 `work\血染钟楼_build_20261110-195352.SC2Map`（70358248 字节），依赖替换为 `bnet:BOTC1/1.0/188805`，注入 61 个素材。
- [x] `tools\botc.cmd inspect` 通过：674 个包内成员，`MapScript.galaxy` 6657019 字节，`BOTC_CustomLogic.galaxy` 2549989 字节，依赖为虚空之遗战役 + `bnet:BOTC1/1.0/188805`。
- [x] 未运行 `botc.cmd test`、未启动星际 II 客户端。
- [x] `CHANGELOG.md` 已在 2026-11-10「角色与机制」追加四条（疯子 / 教授·沙巴洛斯 / 杂耍艺人 / 异教领袖·莽夫）。
- [x] 腾讯文档「星际血染钟楼更新日志」（`DWGpzZEJvanZWWWVD`）已增量插入同一批四条，未整篇覆盖；插入后「角色与机制」与「Bug 修复」标题层级未受影响。
