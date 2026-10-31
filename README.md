# BOTC 说书人地图

星际争霸 II《血染钟楼》真人说书辅助地图的源码、角色规则工具和构建工具。

项目目标是为角色作者提供可审查、可复现的角色规则设计、地图构建和测试工具，而不是依赖编辑器里的一次性手工修改。

仓库提供直接构建测试地图所需的公开基线、Galaxy 脚本、角色规格和工具。角色原图、DDS 源文件、规则原文整理资料和本地 Bank 不单独发布。

## 当前内容

- 说书人工具：赋予能力、发送特定信息、夜间顺序和身份管理。
- 一句话角色 DSL、角色规格审核和接入计划生成。
- SC2Map 解包、脚本写入、UI 内嵌和本地测试工具。
- 克隆后可直接构建的基线地图与公开构建脚本。
- Windows 下可重复运行的 Python 单元测试。

## 仓库边界

仓库保存源码、工具、文档、构建基线，以及授权明确的附加资源；以下内容不会提交：

- 除 `base/BOTC.map` 外的 `.SC2Map`、`.SC2Mod` 和本地 Bank。
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

## 克隆后直接构建

```powershell
git lfs install
git clone https://github.com/FatMan258/SC2Botc.git
cd SC2Botc
git lfs pull

tools\botc.cmd doctor
tools\botc.cmd check
tools\botc.cmd build --script scripts\BOTC_test.galaxy --out work\BOTC_test.SC2Map --split-script
```

成功后得到 `work/BOTC_test.SC2Map`，即可复制到星际 II 测试地图目录。

## 一键同步

日常从 GitHub 同步并构建时，可以直接双击项目根目录：

- `一键同步并构建测试版.cmd`
- `一键同步并构建正式版.cmd`

它们会自动同步 `main`、运行检查、构建地图，把成品放到星际 II 的
`Maps\Test` 目录，并只保留最近两张同步产物。

可上传的游戏素材放入 `assets/game/`，原图放入 `assets/source/`。一键构建会自动
把 `assets/game/` 注入地图包；`assets/source/` 只用于保存和后续加工。
完全不希望上传的临时素材仍可放入 `data/local_assets/`，该目录和生成地图不会进入 Git。

需要把源码修改提交到 GitHub 时，双击：

```text
一键上传到GitHub.cmd
```

它会显示改动、执行检查、要求填写提交说明、提交并推送。地图、Bank、仅本地素材和
本机配置会被自动拦截。

## 配置

默认构建输入已经放在仓库里：

```text
base/BOTC.map
scripts/BOTC.galaxy
scripts/BOTC_test.galaxy
```

通常不再需要设置路径。需要改用其他脚本或地图时，可以通过环境变量覆盖：

```powershell
$env:BOTC_SCRIPT = (Join-Path $PWD "scripts\BOTC_test.galaxy")
$env:BOTC_MAP = (Join-Path $PWD "base\BOTC.map")
$env:BOTC_BUILD_DIR = (Join-Path $PWD "work")
$env:BOTC_SC2_ROOT = "C:\Program Files (x86)\StarCraft II"
```

如 Python 不在 `py` 启动器或 `PATH` 中，可以额外设置：

```powershell
$env:BOTC_PYTHON = "C:\path\to\python.exe"
```

也可以创建不会被 Git 提交的 `tools/python.local.cmd`：

```bat
@echo off
set "BOTC_PYTHON=C:\path\to\python.exe"
```

## 常用命令

```powershell
tools\botc.cmd doctor
tools\botc.cmd inspect
tools\botc.cmd check
tools\botc.cmd build
tools\botc.cmd test "work\地图.SC2Map"

# 使用带新角色测试代码的脚本构建
tools\botc.cmd build --script scripts\BOTC_test.galaxy --out work\BOTC_test.SC2Map

tools\botc.cmd design prompt "每个夜晚，你要选择一名玩家：你得知他的角色。"
tools\botc.cmd design validate roles\role_dsl.example.json
tools\botc.cmd design compile roles\role_dsl.example.json --out role-plan.md
```

运行全部测试：

```powershell
python -m compileall -q tools
python -m unittest discover -s tools\tests -v
```

## GitHub 自动防护

`.github/workflows/tests.yml` 会在每次 push 和 Pull Request 时自动执行：

- Python 编译与单元测试。
- 两份 Galaxy 脚本的括号、编码、函数重复和后置调用前置声明检查。
- 构建环境检查。
- 实际构建正式版和测试版地图。
- 回读构建产物的脚本、触发器和依赖结构。

任何一步失败都会让 GitHub Actions 变红。建议在 GitHub 仓库的
`Settings → Rules / Branch protection` 中把 `test` 设置为合并到 `main`
前的必需检查。

## 目录结构

| 路径 | 用途 |
| --- | --- |
| `base/` | 可直接克隆构建的 SC2Map 基线 |
| `scripts/` | 正式脚本与测试脚本 |
| `roles/` | 角色规格、DSL 示例和接入计划 |
| `data/` | 本地附加资源接口 |
| `assets/` | 可提交的素材源文件与地图运行素材 |
| `probes/` | 独立诊断工具 |
| `tools/` | 构建、检查、角色 DSL 和测试工具 |
| `work/` | 被 Git 忽略的构建和测试输出 |
| `docs/` | 开发和 GitHub 发布指南 |
| `AGENTS.md` | 项目工程约定 |

角色图片源文件放在 `assets/source/`，DDS 等地图运行素材放在 `assets/game/`；
本地 Bank、构建产物和 `data/local_assets/` 不进入本仓库。

## 开发规则

开始修改前阅读 [AGENTS.md](AGENTS.md) 和 [贡献指南](CONTRIBUTING.md)。新角色应先建立受约束的角色 DSL，再实现和测试能力；不要只修改显示文本。

## 许可证

代码许可证尚未确定。素材按项目所有者的发布决定随地图仓库保存；新增素材时应记录
来源，并避免提交账号信息或不属于该地图工程的私有文件。
