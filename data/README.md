# data

本地运行时资源目录。

公开仓库不保存官方角色图片、DDS、音频或私有依赖。需要试验本地附加资源时，
可以放在此目录。

本地构建专用素材放在：

```text
data/local_assets/
```

构建器会递归把其中文件写入地图包，并保持相对路径。例如：

```text
data/local_assets/botc_role148.dds
→ 地图包根目录/botc_role148.dds

data/local_assets/Base.SC2Data/UI/Layout/Custom.SC2Layout
→ 地图包内对应子目录
```

该目录已被 Git 忽略。生成地图也只用于本地测试，不应上传到公开仓库或 Release。

该目录中的游戏素材默认不进入 Git。
