# 角色设计计划：梦魇贩子

- 索引：148
- 阵营：minion / evil
- 时机：every_night
- 频率：always
- 目标：1 名玩家和 1 个角色
- 夜序分类：interference
- 规则文本：每个夜晚，你要选择一名其他存活玩家和一个角色。如果他是该角色，他中毒直到下个黄昏；否则你得知他不是该角色。
- 角色介绍：一个收集恐惧、并把猜中的梦魇卖给受害者的爪牙。梦魇贩子会用身份作为赌注：猜中时让目标的处境恶化，猜错时只能确认这条线索并不成立。

## 效果
- 放置 token dream_poison，持续 until_dusk
- 发送信息：如果目标的真实角色与所选角色不同，梦魇贩子得知他不是该角色。

## Token
- 中毒（梦魇贩子）（梦魇毒 / dream_poison）：目标的角色能力不生效；图标：botc_tk17.dds；放置：梦魇贩子猜中目标真实角色时放置，并移除他上一次放置的梦魇毒；移除：下个黄昏、梦魇贩子离场或新局开始时移除；可见性：storyteller

## 相克规则
- 当前未声明特殊相克；相克梳理仍需逐角色人工复核

## 建议角色数据
g_roleName[148] = "梦魇贩子"; g_roleTeam[148] = 2; g_roleAlign[148] = 1;
g_roleAct[148] = 1;
g_roleTargets[148] = 1;
g_noAllFirst[148] = 32;
g_noAllOther[148] = 13;
// TODO: 按官方夜间顺序表，将角色插入 投毒者 的 after 位置

## 必须接入的位置
- [ ] BOTC_HasAbility
- [ ] BOTC_AbilityWorks
- [ ] BOTC_AbilitySeat
- [ ] BOTC_SkillOpen
- [ ] BOTC_SkillConfirm
- [ ] BOTC_SkillPickSeat
- [ ] BOTC_PickChoose
- [ ] g_pickSlotRole
- [ ] BOTC_TargetIsLiving
- [ ] 目标死亡时拒绝确认
- [ ] BOTC_CanWakeAt
- [ ] BOTC_NightOrder
- [ ] token 放置
- [ ] token 移除
- [ ] 来源离场清理
- [ ] 第二局清理
- [ ] 角色能力文本
- [ ] 详情页文本
- [ ] 身份图
- [ ] 夜序图
- [ ] token 图

## 规则测试
- [ ] 健康来源猜中目标角色：目标获得梦魇毒，到下一个黄昏移除
- [ ] 健康来源猜错：梦魇贩子收到他不是该角色的私聊信息
- [ ] 目标死亡或梦魇贩子无法选择死亡玩家时拒绝确认
- [ ] 梦魇贩子中毒或醉酒：不放置新毒，也不自动发送真假信息
- [ ] 梦魇贩子死亡、离场或身份变化：梦魇毒立即移除
- [ ] 换座位、换说书人和第二局后不保留旧目标
