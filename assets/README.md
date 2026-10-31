# Assets

- `source/`：角色原图、PSD/PNG 等加工素材，不进入地图包。
- `game/`：DDS、SC2Layout 等运行时素材，构建时按相对路径注入地图包根目录。

`assets/` 中的图片通过 Git LFS 管理。完全不想上传的临时素材仍放在
`data/local_assets/`。
