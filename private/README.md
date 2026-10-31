# BOTC 私有依赖

这个目录只生成 `BOTC_Private_Core.SC2Mod`。

- 黑名单数据、检查函数和 MapInit 触发器都位于依赖中，不在地图主脚本中。
- 正式地图和测试地图共用已上传依赖 `bnet:BOTC1/1.0/188805`。
- `BOTC_Private.template.SC2Mod` 只作为模块容器模板。
- `data/private/ban_handles.txt` 保存本地黑名单，不提交到仓库。
- `private/dependency_id.txt` 保存当前上传的 `BOTC1` 完整 ID。

发布时先上传正式依赖，再把地图 `DocumentInfo` 中的本地依赖路径替换为
Battle.net 依赖 ID。依赖不是加密格式；它用于防止普通地图使用者直接修改，
不能防御能够解包、修改并重新发布整个地图的人。
