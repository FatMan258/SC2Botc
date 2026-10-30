# BOTC 说书人地图

星际争霸 II《血染钟楼》真人说书辅助地图的源码、角色规则工具和构建工具。

项目目标是为角色作者提供可审查、可复现的角色规则设计、地图构建和测试工具，而不是依赖编辑器里的一次性手工修改。

本仓库只发布编写的源码和工具，不包含角色图片、DDS、官方规则原文、地图文件或 Bank。构建地图时需要在本地自行提供基础地图、UI 资源和图标资源。

## 当前内容

- 说书人工具：赋予能力、发送特定信息、夜间顺序和身份管理。
- 一句话角色 DSL、角色规格审核和接入计划生成。
- SC2Map 解包、脚本写入、UI 内嵌和本地测试工具。
- Windows 下可重复运行的 Python 单元测试。

## 仓库边界

仓库保存源码、工具、文档和授权明确的资源；以下内容不会提交：

- `.SC2Map`、`.SC2Mod` 和本地 Bank。
- 构建目录、测试地图、地图解包临时目录。
- 私人项目记忆、账号信息和本机绝对路径。
- 未经确认授权的第三方图片、音频或模型。

发布用地图应通过 GitHub Releases 提供，不直接塞进 Git 历史。

## 环境要求

- Windows 10/11。
- Python 3.10 或更高版本。
- StarCraft II 与银河编辑器。
- Git；二进制资源需要 Git LFS。

安装 Git LFS：

```powershell
git lfs install
```

## 配置

地图和星际 II 的安装路径不写死在仓库里，通过环境变量指定：

```powershell
$env:BOTC_SCRIPT = "C:\path\to\BOTC_脚本_粘贴用.txt"
$env:BOTC_MAP = "C:\path\to\base.SC2Map"
$env:BOTC_UI_MOD = "C:\path\to\UIHIDE55.SC2Mod"
$env:BOTC_BUILD_DIR = (Join-Path $PWD "build")
$env:BOTC_SC2_ROOT = "C:\Program Files (x86)\StarCraft II"
```

如 Python 不在 `py` 启动器或 `PATH` 中，可以额外设置：

```powershell
$env:BOTC_PYTHON = "C:\path\to\python.exe"
```

也可以创建不会被 Git 提交的 `BOTC_Tools/python.local.cmd`：

```bat
@echo off
set "BOTC_PYTHON=C:\path\to\python.exe"
```

## 常用命令

```powershell
BOTC_Tools\botc.cmd inspect
BOTC_Tools\botc.cmd check
BOTC_Tools\botc.cmd build
BOTC_Tools\botc.cmd test "build\地图.SC2Map"

BOTC_Tools\botc.cmd design prompt "每个夜晚，你要选择一名玩家：你得知他的角色。"
BOTC_Tools\botc.cmd design validate BOTC_Tools\role_specs\role_dsl.example.json
BOTC_Tools\botc.cmd design compile BOTC_Tools\role_specs\role_dsl.example.json --out role-plan.md
```

运行全部测试：

```powershell
python -m compileall -q BOTC_Tools
python -m unittest discover -s BOTC_Tools\tests -v
```

## 目录结构

| 路径 | 用途 |
| --- | --- |
| `BOTC_Tools/` | 构建、检查、角色 DSL 和测试工具 |
| `BOTC_Tools/role_specs/` | 角色规格、DSL 示例和接入计划 |
| `BOTC_UI导入/` | 可内嵌的 UI 布局资源 |
| `docs/` | 开发和 GitHub 发布指南 |
| `AGENTS.md` | 项目工程约定 |

完整地图脚本、地图文件、角色图片和规则原文由使用者在本机提供，不进入本仓库。

## 开发规则

开始修改前阅读 [AGENTS.md](AGENTS.md) 和 [贡献指南](CONTRIBUTING.md)。新角色应先建立受约束的角色 DSL，再实现和测试能力；不要只修改显示文本。

## 许可证

许可证尚未确定。在仓库公开前必须完成以下确认：

- 代码采用哪种开源许可证。
- 角色图片、DDS、音频和其他素材是否允许再分发。
- 地图名称、规则文本和第三方角色设计是否符合对应授权。

在许可证确定前，默认保留全部权利，不应直接设为公开仓库。
