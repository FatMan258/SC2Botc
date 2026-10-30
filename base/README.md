# base

可重复构建的地图基线。

- `BOTC.map`：公开测试基线，已包含地图触发器、UI 和必要包内资源。
- 构建时只复制并修改输出地图，不直接修改此文件。
- `BOTC.map` 通过 Git LFS 保存。

默认路径由 `tools/botc_config.py` 指向此文件，也可以用 `BOTC_MAP` 覆盖：

```powershell
$env:BOTC_MAP = (Join-Path $PWD "base\BOTC.map")
```
