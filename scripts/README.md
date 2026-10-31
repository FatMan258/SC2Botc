# scripts

Galaxy 主脚本源文件。

- `BOTC.galaxy`：唯一主脚本，默认用于构建正式地图。

文件保持 UTF-8 BOM 和 CRLF。默认路径由 `tools/botc_config.py` 指定，也可以用
`BOTC_SCRIPT` 覆盖。

```powershell
tools\botc.cmd build
tools\botc.cmd build --out work\BOTC_BOTC1.SC2Map
```
