# 贡献指南

## 开始修改前

1. 阅读 `AGENTS.md` 和 `BOTC_Tools/README.md`。
2. 一个分支只处理一个功能或一个 Bug。
3. 新角色先创建 `BOTC_Tools/role_specs` 下的 JSON 规格。
4. 不要提交地图、Bank、账号信息、构建产物或未授权素材。

## 修改流程

```powershell
BOTC_Tools\botc.cmd check
python -m unittest discover -s BOTC_Tools\tests -v
BOTC_Tools\botc.cmd design validate BOTC_Tools\role_specs\role_dsl.example.json
```

涉及角色时还需要：

```powershell
BOTC_Tools\botc.cmd role audit BOTC_Tools\role_specs\角色规格.json
BOTC_Tools\botc.cmd design compile BOTC_Tools\role_specs\角色规格.json --out role-plan.md
```

如果修改会影响游戏内行为，必须构建测试地图并在游戏中验收。只通过静态检查不能视为完成。

## Galaxy 文件约定

- 主脚本保持 UTF-8 BOM 和 CRLF。
- 字符串使用直引号，不使用弯引号。
- 数组维度写在类型后，例如 `int[14] g_vote;`。
- 条件必须是 `bool`，不使用三元表达式。
- 不整份重排主脚本，只做最小定向修改。
- 全局变量和函数声明放在文件靠前位置。

## 角色接入要求

- 明确时机、目标、存活限制、持续时间、频率和相克关系。
- token 必须说明名称、短名、作用、放置时机、移除时机、可见性和清理条件。
- 能力必须经过统一能力层，不能只匹配真实角色索引。
- 检查中毒、醉酒、失去能力、换座位、换说书人和第二局重置。
- 角色在当前板子上时，必须能在说书人的【赋予能力】窗口选到。

## 提交前

- 检查 `git status`，确认没有地图、Bank、缓存或临时文件。
- 说明修改了什么、如何测试以及仍未验证的部分。
- 不在 Issue、提交或截图中公开账号凭据和私有依赖。
