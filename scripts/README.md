# scripts

Galaxy 主脚本源文件。

- `BOTC.txt`：正式版本，默认用于构建。
- `BOTC_test.txt`：包含新角色和实验改动的测试版本。

文件保持 UTF-8 BOM 和 CRLF。默认路径由 `tools/botc_config.py` 指定，也可以用
`BOTC_SCRIPT` 覆盖。

```powershell
tools\botc.cmd build
tools\botc.cmd build --script scripts\BOTC_test.txt --out work\BOTC_test.SC2Map
```
