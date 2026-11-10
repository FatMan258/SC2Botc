# 疯子 · 假科学怪人能力改为「按中毒 / 醉酒处理」

## 1. 目标

把科学怪人发给【疯子】的那份「假善良能力」，从当前的「确认后完全不结算、直接丢弃」
改成与中毒 / 醉酒一致的行为：

- 面板照常打开，疯子照常选目标；
- 流程照走（说书人照常收到该角色应有的记录、信息位照常说书人填答案发给疯子）；
- **效果一律不生效**（例如假【守夜人】选了一名玩家，对方收不到任何信息）；
- 不再额外弹「能力无效」这种一眼假的提示文案。

## 2. 现状（改动前）

| 位置 | 现状 |
| --- | --- |
| `BOTC_SkillWorks(q)`（`scripts/BOTC.galaxy:35727`） | 中毒 / 酒鬼 / 提线木偶 / 活尸的统一闸门，**不认识假能力** |
| `BOTC_SkillConfirm`（56227） | 56276-56296 有一整段假能力拦截：校验目标 → 清状态 → 关面板 → `BOTC_PmStore("…能力无效，不产生任何结算")` → `g_lunFakeAct[p]=false` → `return`（**不结算**） |
| `BOTC_WakeApply`（52597-52617） | 假能力短路：设 `g_awake` / `g_wakeCurrentOrd` / `g_wokeTonight`，清技能槽，提示「不会产生任何结算」，`BOTC_SkillOpen(q)`，`return` |
| `BOTC_SkillOpen`（53227-53237） | 假能力短路：清技能槽后打开通用面板，交给 `BOTC_SkillRender()` |
| `BOTC_LunFakeRoleSet`（≈49930-49945） | 设置假能力时 `BOTC_PmStore` 写「结算不产生任何效果」 |
| `g_lunFakeAct[14]`（1164） | 「这一夜正在按假能力唤醒 / 行动」标记；换夜由 `BOTC_AutoWakeReset`（50003）清，收回唤醒由 52585 清 |

## 3. 目标行为（改动后）

1. 假能力期间 `BOTC_SkillWorks(q)` 返回 `false` → 所有效果角色自动落到它们**既有的**
   「中毒 / 醉酒 → 这一次无效」分支（僧侣 57228、投毒者 57244 等都是这个写法），
   直接复用现成的失效语义，不新造一套判定。
2. `BOTC_SkillConfirm` 的假能力拦截整段删除，让确认走正常角色结算；
   结算结束后立刻把 `g_lunFakeAct[p]` 撤掉（否则整夜 `BOTC_ActRoleOf` 会一直返回假角色、
   `BOTC_SkillWorks` 会一直为假）。
3. `BOTC_WakeApply` / `BOTC_SkillOpen` 的短路逻辑**保留**（它只负责「照常唤醒 + 开面板」，
   并且顺带跳过理发师这类角色专用尾部，避免假能力触发别的角色的分支），只改文案。
4. 不改 `BOTC_SeatImpaired` / `BOTC_SeatImpairedRaw`（会污染全局中毒判定）。

## 4. 具体改动

### 4.1 `BOTC_SkillWorks`（35727-35748）

在 `g_liveCorpse` 判断之后、`g_boffinActing` 之前插入：

```galaxy
    // 【疯子·假能力】（用户 2026-11-10）：科学怪人发给疯子的那份假能力按中毒 / 醉酒处理 ——
    //   面板照常打开、说书人照常给信息、流程照走，但这一次的效果不生效。
    if (g_lunFakeAct[q]) {
        return false;
    }
```

### 4.2 `BOTC_SkillConfirm`（56227 起）

1. 删除 56276-56296 的假能力拦截整段。
2. 把定义行 `void BOTC_SkillConfirm (int p) {` 改名为 `void BOTC_SkillConfirmCore (int p) {`。
3. 在其**上方**插入原型与同名包装（原型在 2935 已有，名字不用变）：

```galaxy
void BOTC_SkillConfirmCore (int p);

// 【疯子·假能力】（用户 2026-11-10）：假能力按中毒 / 醉酒处理 —— 结算照常走完，
//   但 BOTC_SkillWorks 在此期间一律返回 false，所以效果不生效；确认完立刻撤掉行动标记。
void BOTC_SkillConfirm (int p) {
    BOTC_SkillConfirmCore(p);
    if (p >= 1 && p <= 13 && g_lunFakeAct[p]) {
        g_lunFakeAct[p] = false;
        BOTC_GrimRender(g_teller);
    }
}
```

### 4.3 文案与注释

- 52612：`"（假能力「X」，不会产生任何结算）"` → `"（假能力「X」，按中毒 / 醉酒处理：效果不生效）"`。
- 52613：`"确认后不产生任何效果"` → `"这次能力按中毒 / 醉酒处理，效果不生效"`。
- 53223-53224 注释：把「确认时由 BOTC_SkillConfirm 顶部拦下，不产生任何结算」
  改为「按中毒 / 醉酒处理：`BOTC_SkillWorks` 期间返回 false，效果不生效」。
- 1164 行 `g_lunFakeAct` 注释：`（结算不产生任何效果）` → `（按中毒 / 醉酒处理：面板照常，效果不生效）`。
- ≈49943 的 `BOTC_PmStore`：`结算不产生任何效果` → `这次能力按中毒 / 醉酒处理，效果不生效`。

## 5. 验收

- `tools\botc.cmd check` 通过（含 CRLF + UTF-8 BOM 检查）。
- `tools\botc.cmd build` 成功。
- `tools\botc.cmd inspect`：`MapScript.galaxy` + `BOTC_CustomLogic.galaxy` 存在，
  依赖为 `bnet:BOTC1/1.0/188805`，包内成员数符合预期（约 615）。
- 人工回归（用户实测）：
  1. 疯子拿到假【守夜人】→ 面板打开、选人、确认 → 目标玩家**收不到**信息，也不报错。
  2. 疯子拿到假【占卜师】→ 确认后说书人答题框照常弹出，疯子照常收到那份（可能为假的）信息。
  3. 疯子拿到假【僧侣】→ 确认后说书人私聊提示这一次按中毒 / 醉酒无效，目标不获得保护。
  4. 不出现「能力无效 / 不产生任何结算」之类提示。
  5. 同一夜疯子不会被重复唤醒（`g_lunFakeActed`），确认后魔典恢复显示他本人身份。
  6. 第二局 / 换夜不残留 `g_lunFakeAct`。

## 6. 收尾

- `CHANGELOG.md` 2026-11-10「角色与机制」中【疯子 × 科学怪人】条目改为
  「按中毒 / 醉酒处理：面板与流程照常，效果一律不生效」。
- 用 doc-mcp 增量同步腾讯文档「星际血染钟楼更新日志」（file_id `DWGpzZEJvanZWWWVD`）。

## 7. 不在本次范围

- 不新增/修改任何角色数据、板子、token。
- 不恢复自动裁量，不启动游戏客户端。
