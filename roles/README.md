# roles

角色作者使用的结构化规格目录。

- `role_dsl.example.json`：一句话角色 DSL 示例。
- `role_148.example.json`：脚本接入计划示例。

推荐流程：

```powershell
tools\botc.cmd design prompt "一句话角色能力"
tools\botc.cmd design validate roles\角色规格.json
tools\botc.cmd design compile roles\角色规格.json --out roles\角色计划.md
```

详细格式见 [`docs/ROLE_DSL.md`](../docs/ROLE_DSL.md)。
