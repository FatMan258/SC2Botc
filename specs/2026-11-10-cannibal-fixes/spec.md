# 食人族（74）互动修复规格

日期：2026-11-10
唯一改动文件：`scripts/BOTC.galaxy`
关联规则：`AGENTS.md` 第 9 / 12 / 13 / 19 节

## 0. 目标与范围

修复四项已确认缺陷：

1. 杂耍艺人（58）补充能力在附加能力唤醒链上会重复唤醒。
2. 食人族经教授（30）/ 沙巴洛斯（45）复活后不会补发“最近死于处决者”的能力。
3. 食人族获得疯子（38）能力后，缺少「告知是某个恶魔 → 按疯子夜序唤醒攻击 → 唤醒恶魔并告知其身份与目标」的完整链。
4. 食人族因异教领袖（106）/ 莽夫（37）改变阵营后，缺少“另一名无法转变阵营的玩家在其转回原阵营前死于处决 → 锁定当前阵营”的判定。

不在本次范围：
- “公主”角色在地图中不存在（仅在百科文本 `g_tipLine` 的 17299 处有相克描述），本规格不新增角色，不伪造逻辑。
- 不恢复智能说书、不改构建链、不新建备份。

## 1. 新增全局状态（声明区，`g_cannFedSeat` 一带）

```galaxy
// 【食人族 × 异教领袖 / 莽夫 · 阵营锁定】（用户 2026-11-10）
int[14]     g_cannOrigAlign;   // 首次因莽夫 / 异教领袖改变阵营前记录的原阵营（-1 = 未记录）
bool[14]    g_cannLocked;      // 已锁定：保持当前阵营，不再被改
// 【食人族 × 疯子】（用户 2026-11-10）
bool[14]    g_cannLun;         // 食人族持有的疯子能力处于“认知恶魔”状态
int[14]     g_cannLunDemon;    // 该座位以为自己是哪个恶魔（角色索引；-1 = 未选）
// 【食人族复活补发】（用户 2026-11-10）
bool[14]    g_cannRestore;     // 本座位复活后需要在下一夜重新补发最近处决者的能力
```

`BOTC_ResetGameVars()` 的新局清理循环中（与 `g_grantActing` / `g_juggDone` 同段）追加：

```galaxy
g_cannOrigAlign[i] = -1;
g_cannLocked[i] = false;
g_cannLun[i] = false;
g_cannLunDemon[i] = -1;
g_cannRestore[i] = false;
```

## 2. 修复三：杂耍艺人（58）不再重复唤醒

文件位置：`BOTC_GrantWakeOrder(int q)`，在现有 `if (role == 147) { return 0; }` 之后、`return BOTC_GrantNightOrder(q);` 之前插入：

```galaxy
// 【杂耍艺人（58）】只在“当天公开猜过、且这一局还没拿过结果”的那一夜唤醒一次；
//   唯一的例外是杂耍艺人本人当天猜测后当天被处决 → 食人族当晚直接替他拿结果。
if (role == 58 && g_juggUsed[q]) {
    return 0;
}
if (role == 58 && !g_juggDone[q] && !BOTC_JugglerDiedAfterGuess()) {
    return 0;
}
```

实现约束：
- `BOTC_JugglerDiedAfterGuess` 的真实签名（是否带参数）以代码现状为准；若为无参 bool 函数直接调用，若需座位参数则按其定义传入“该杂耍艺人座位”。
- 不改 `BOTC_GrantNightOrder` 的 58 分支（首夜放行 + 死亡当天顺延仍是正确行为）。
- 不改原生路径的 `BOTC_WakeSkipNow` 两行。

## 3. 修复二：教授 / 沙巴洛斯复活后补发能力

### 3.1 复活入口挂载

`BOTC_RestoreOneShot(int q)` 尾部（该函数结尾 `}` 之前）追加：

```galaxy
// 【食人族（74）复活补发】（用户 2026-11-10）：食人族经教授 / 沙巴洛斯复活后，
//   重新获得“最近一次死于处决的玩家”的能力；跨天也算，不再要求处决发生在当天。
if (BOTC_HasAbility(q, 74) && g_cannFedSeat >= 2 && g_cannFedSeat <= 13) {
    if (BOTC_SeatTrueRole(g_cannFedSeat) >= 0 && BOTC_SeatTrueRole(g_cannFedSeat) <= 163) {
        g_cannPending = 1;
        g_cannRestore[q] = true;
        BOTC_PmStore(g_teller, "【食人族】" + BOTC_NameStr(q) + " 复活 → 下一夜重新获得最近一次处决者「" + BOTC_NameStr(g_cannFedSeat) + "」的能力。");
    }
}
```

### 3.2 夜间补发放宽“当天处决”限制

`BOTC_PreGrantStep()` 的食人族分支内：

- 自动补发条件由
  `g_cannFedSeat >= 2 && g_cannFedSeat <= 13 && g_cannFedDay == g_dayNum && BOTC_SeatImpaired(q) == false`
  改为
  `g_cannFedSeat >= 2 && g_cannFedSeat <= 13 && (g_cannFedDay == g_dayNum || g_cannRestore[q]) && BOTC_SeatImpaired(q) == false`。
- 在 `g_cannDoneNight = g_nightNum;` 之后追加 `g_cannRestore[q] = false;`。
- `BOTC_CannPickOpen(q); return true;` 之前也追加 `g_cannRestore[q] = false;`（防止标记残留到下一夜重复弹面板）。

### 3.3 边界

- 复活当晚若 `g_cannDoneNight == g_nightNum`（本夜已发放过），`g_cannPending` 保留，下一夜补发，不重复发放。
- 食人族复活但 `g_cannFedSeat` 无效（0 / 不在 2..13 / 角色索引非法）→ 不发、不弹面板，只保持沉默。

## 4. 修复一：疯子（38）完整互动

### 4.1 获得能力时告知“你是某个恶魔”

在 `BOTC_AttachGrant`（附加能力统一落点）里 `g_grantRoleBy[q] = role + 1;` 之后追加：

```galaxy
// 【食人族吃到疯子】（用户 2026-11-10）：告知他“现在是剧本上的某个恶魔”，
//   并按疯子的夜序参与唤醒；由说书人在恶魔网格里指定是哪个恶魔。
if (role == 38 && BOTC_HasAbility(q, 74)) {
    g_cannLun[q] = true;
    g_cannLunDemon[q] = -1;
    g_cannSeat = q;
    g_cannSrc = 0;
    BOTC_CannOpen(38);
}
```

实现约束：
- `BOTC_CannOpen` / `BOTC_CannPick` 的现有签名与 `g_cannKind` 语义按代码现状复用；`BOTC_CannPick` 选中后除原有提示外，追加 `g_cannLunDemon[g_cannSeat] = 选中的角色索引;`。
- 不在 `BOTC_AttachGrantOrNest` 里重复挂钩，避免哲学家 / 炼金术士二次选择路径重复弹窗。

### 4.2 让疯子判定认这个座位

- `BOTC_IsLunatic(int q)` 追加 `if (g_cannLun[q]) { return true; }`（放在 token 49 判断之后、真实角色判断之前）。
- `BOTC_RealLunaticSeat()` 与 `BOTC_LunaticActingSeat()` 中判定“假装的那个”的条件
  `g_tokOn[... + 70] || g_tokOn[... + 97]`
  追加 `|| g_cannLun[i]`，保证食人族被归入 `any` / `anyOk` 桶，而不是抢走真疯子的优先位。

### 4.3 攻击结算与恶魔告知

`BOTC_LunaticPickNotify(int q)` 开头（参数校验之后）插入：

```galaxy
// 【食人族×疯子】（用户 2026-11-10）：食人族吃到的疯子能力行动后，恶魔要知道
//   “这名玩家是疯子”以及他攻击了谁；攻击不产生死亡。
if (lu >= 2 && g_cannLun[lu]) {
    BOTC_PmStore(g_teller, "【食人族×疯子】" + BOTC_NameStr(lu) + " 选择了" + BOTC_NameStr(q) + "，不产生死亡。");
    if (!BOTC_SeatImpaired(lu)) {
        BOTC_PmInfoDemons("【信息】" + BOTC_NameStr(lu) + " 是疯子，他选择了" + BOTC_NameStr(q) + "。");
    }
    else {
        BOTC_PmStore(g_teller, "【食人族×疯子】" + BOTC_NameStr(lu) + " 中毒/酒鬼 → 不发送给恶魔。");
    }
    return;
}
```

实现约束：
- 该分支必须在原有“疯子选择了 X / PmInfoDemons”之前 return，避免同一动作发两条。
- 攻击不写任何死亡 token、不走 `BOTC_DeathBlocker`。
- 若 `BOTC_SkillConfirm` 对角色 38 已有专用结算，需要确认它调用了 `BOTC_LunaticPickNotify`；没有则在角色 38 的确认分支补一行调用（不新增死亡逻辑）。

## 5. 修复四：异教领袖 / 莽夫阵营锁定

### 5.1 记录原阵营

在两个真正改动食人族自身阵营的入口，改阵营前记录一次：

- `BOTC_GoonTouch(...)` 中，`BOTC_SetReg(g, -1, ca);` 之前
- `BOTC_CultChoiceAnswer(...)` 中，`BOTC_SetReg(q, -1, al);`（或对应写阵营调用）之前

统一插入：

```galaxy
// 【食人族 × 异教领袖 / 莽夫】（用户 2026-11-10）：第一次被改阵营前记住原阵营。
if (BOTC_HasAbility(q, 74) && g_cannOrigAlign[q] < 0 && BOTC_SeatRegAlign(q) != 目标阵营) {
    g_cannOrigAlign[q] = BOTC_SeatRegAlign(q);
}
```

（`q` / `g` 按各函数实际座位变量名替换，`目标阵营` 分别为 `ca` / `al`。）

### 5.2 已锁定时拒绝改阵营

- `BOTC_GoonTouch`：在算出 `ca` 之后，若 `g_cannLocked[g]` 且 `BOTC_SeatRegAlign(g) != ca`，把 `ca` 改回当前阵营，并向说书人私聊一行：
  「【食人族×莽夫】X 的阵营已锁定为 <当前阵营>，本次不改变。」
- `BOTC_CultChoiceAnswer`：同样在算出 `al` 之后，若 `g_cannLocked[q]` 且 `BOTC_SeatRegAlign(q) != al`，把 `al` 改回当前阵营并私聊说书人。
- token 14 / 15 等阵营标记仍按最终生效阵营同步，不留下“显示改了、实际没改”的脏标记。

### 5.3 处决后锁定判定

在 `BOTC_CannExecHooks(int q)` 内、处决记录写完之后追加 `BOTC_CannLockCheck(q);`，并新增函数：

```galaxy
// 这个座位自己能不能被改阵营：异教领袖 / 莽夫能力持有者算“能转变”。
bool BOTC_AlignCanChange (int q) {
    if (q < 1 || q > 13) { return false; }
    return (BOTC_HasAbility(q, 37) || BOTC_HasAbility(q, 106));
}

// 【食人族 × 异教领袖 / 莽夫】（用户 2026-11-10）：食人族当前不在原阵营时，
//   另一名无法转变阵营的玩家死于处决 → 锁定他现在的阵营。
void BOTC_CannLockCheck (int dead) {
    int i;
    int al;
    if (dead < 2 || dead > 13) { return; }
    if (BOTC_AlignCanChange(dead)) { return; }
    for (i = 2; i <= 13; i += 1) {
        if (!g_seatOn[i] || BOTC_SeatDead(i)) { continue; }
        if (i == dead) { continue; }
        if (g_cannOrigAlign[i] < 0 || g_cannLocked[i]) { continue; }
        if (!BOTC_HasAbility(i, 74)) { continue; }
        al = BOTC_SeatRegAlign(i);
        if (al == g_cannOrigAlign[i]) { continue; }
        g_cannLocked[i] = true;
        BOTC_PmStore(g_teller, "【食人族】" + BOTC_NameStr(i) + " 仍是 " + BOTC_AlignName(al) + " 阵营时，无法转变阵营的 " + BOTC_NameStr(dead) + " 死于处决 → " + BOTC_NameStr(i) + " 的阵营锁定为 " + BOTC_AlignName(al) + "。");
    }
}
```

函数原型需加入文件头部的函数声明区（与 `BOTC_CannExecHooks` 声明同段），避免“先用后定义”编译失败。

### 5.4 边界

- 食人族在“改变后、锁定前”自己转回原阵营 → 不锁定；`g_cannOrigAlign` 保留（下次再改仍以同一原阵营为基准）。
- 食人族自己死于处决 → 不锁定（`i == dead` 跳过）。
- 死者本身持有 37 / 106 → 视为“能转变阵营”，不触发锁定。
- 已锁定的食人族不会再被 37 / 106 改阵营，但仍可被其他机制改（本规格不扩展）。

## 6. 验证步骤

1. `tools\botc.cmd check` —— 必须无语法错误（重点：新增函数原型、`bool` 条件、数组维度）。
2. `tools\botc.cmd build` —— 构建成功。
3. `tools\botc.cmd inspect` —— 核对：
   - `MapScript.galaxy` 存在且大小合理；
   - 自定义脚本首尾标记与 `BOTC_Init()` 存在；
   - 内嵌 UI 文件在；
   - 依赖仍为 `bnet:BOTC1/1.0/188805`。
4. 不运行 `botc.cmd test`，不启动星际 II。
5. 人工核对（用户实机）：
   - 杂耍艺人：食人族拿到能力后，没猜的那一夜不唤醒；猜过的当夜只唤醒一次；次日不再唤醒。
   - 教授 / 沙巴洛斯：复活食人族，下一夜自动获得最近处决者能力（说书人私聊有提示）。
   - 疯子：食人族拿到 38 后弹恶魔网格 → 选中后本人收到“你现在把自己当成恶魔 X”；疯子夜序被唤醒选人；随后恶魔收到“X 是疯子，他选择了 Y”；无人死亡。
   - 异教领袖 / 莽夫：改阵营后，另一名无 37/106 的玩家被处决 → 说书人收到锁定提示；之后再次改阵营被拒绝。

## 7. 收尾

- `CHANGELOG.md` 当日“角色与机制”分类追加四条（疯子互动 / 复活补发 / 杂耍艺人唤醒 / 阵营锁定）。
- doc-mcp 增量同步腾讯文档「星际血染钟楼更新日志」（file_id `DWGpzZEJvanZWWWVD`），只插入新增条目。
- 不创建备份、不更新项目记忆文件。
