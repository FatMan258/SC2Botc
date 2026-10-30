# 第一次上传到 GitHub

建议第一次先创建 **Private** 仓库，确认许可证和素材授权后再公开。

## 1. 安装和登录

仓库已经启用 Git LFS。先确保本机执行过：

```powershell
git lfs install
```

第一次使用 GitHub 时，推荐安装 GitHub Desktop 并用浏览器登录。不要把自己的一次性密码、访问令牌或 Cookie 发给任何人。

## 2. 创建远程仓库

在 GitHub 点击 **New repository**：

- 名称建议：`botc-storyteller-map`
- 可见性：先选 **Private**
- 不要勾选自动创建 README、`.gitignore` 或 LICENSE

创建后复制仓库的 HTTPS 地址。

## 3. 关联并推送

在项目根目录执行：

```powershell
git remote add origin https://github.com/你的用户名/botc-storyteller-map.git
git push -u origin main
```

如果使用 GitHub Desktop，可以直接选择 **Add existing repository**，发布时再选择 **Publish repository**。

## 4. 地图和大型资源

- `.SC2Map`、`.SC2Mod`、Bank 和构建目录不会进入普通 Git 提交。
- DDS、PNG、音频和 DLL 已配置为 Git LFS。
- 可玩的成品地图通过 GitHub 的 **Releases** 上传，不放进源码目录。

## 5. 公开前检查

- 确定 LICENSE，并与素材授权一致。
- 检查截图、日志和文档中没有 Battle.net 账号、路径或私人信息。
- 运行全部测试。
- 创建第一个版本标签，例如 `v0.1.0-test`。
- 在 Release 中附加测试地图和变更说明。

## 6. 日常修改

```powershell
git switch -c feature/new-role
git status
git add .
git commit -m "feat: add new role prototype"
git push -u origin feature/new-role
```

然后在 GitHub 创建 Pull Request，确认测试通过后再合并到 `main`。
