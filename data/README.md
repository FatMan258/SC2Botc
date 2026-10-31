# data

本地运行时资源目录。

可发布素材统一放在仓库根目录的 `assets/`：

```text
assets/source/   原始 PNG / PSD 等加工素材，不注入地图
assets/game/     DDS 等地图运行素材，构建时自动注入地图根目录
```

完全不想上传的临时素材放在：

```text
data/local_assets/
```

构建器会递归把 `assets/game/` 和 `data/local_assets/` 中的文件写入地图包，
并保持相对路径。例如：

```text
assets/game/botc_role148.dds
→ 地图包根目录/botc_role148.dds

data/local_assets/Base.SC2Data/UI/Layout/Custom.SC2Layout
→ 地图包内对应子目录
```

`data/local_assets/` 已被 Git 忽略，`assets/` 则用于需要随仓库发布和分享的素材。
