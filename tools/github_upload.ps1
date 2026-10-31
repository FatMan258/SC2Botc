param(
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

function Invoke-Git {
    param([string[]]$CommandArgs)
    & git @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git $($CommandArgs -join ' ') 失败（退出码 $LASTEXITCODE）"
    }
}

function Unstage-All {
    & git restore --staged -- .
}

try {
    Write-Host "== BOTC 一键上传 GitHub ==" -ForegroundColor Cyan
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "找不到 Git。"
    }
    if (-not (git config user.name)) {
        throw "未配置 Git user.name。请先在仓库中运行 git config --local user.name `"你的名字`"。"
    }
    if (-not (git config user.email)) {
        throw "未配置 Git user.email。请先配置 GitHub noreply 邮箱。"
    }

    $branch = (& git branch --show-current).Trim()
    if (-not $branch) {
        throw "当前处于 detached HEAD，无法自动上传。"
    }
    $changes = @(& git status --porcelain)
    if ($changes.Count -eq 0) {
        Write-Host "没有需要上传的修改。" -ForegroundColor Yellow
        exit 0
    }

    Write-Host "当前分支：$branch" -ForegroundColor Cyan
    Write-Host "待处理修改：" -ForegroundColor Cyan
    $changes | ForEach-Object { Write-Host "  $_" }
    Write-Host ""
    & git diff --stat

    $message = Read-Host "请输入提交说明"
    if (-not $message.Trim()) {
        throw "提交说明不能为空。"
    }
    $confirm = Read-Host "确认运行检查、提交并上传？输入 y 继续"
    if ($confirm -notmatch '^(?i)y(es)?$') {
        Write-Host "已取消。" -ForegroundColor Yellow
        exit 0
    }

    Write-Host "[1/4] 暂存修改..."
    Invoke-Git @("add", "-A")
    $staged = @(& git diff --cached --name-only)
    if ($staged.Count -eq 0) {
        throw "没有可提交的内容。"
    }

    $forbidden = $staged | Where-Object {
        $_ -match '\.(SC2Map|SC2Bank|bank)$' -or
        $_ -match '(^|/)work/' -or
        $_ -match '(^|/)data/local_assets/' -or
        $_ -match '(^|/)\.env(\.|$)' -or
        $_ -match 'python\.local\.cmd$' -or
        $_ -match '(^|/)node_modules/'
    }
    if ($forbidden) {
        Write-Host "发现不应上传的文件：" -ForegroundColor Red
        $forbidden | ForEach-Object { Write-Host "  $_" }
        Unstage-All
        throw "上传已停止。请把这些文件加入 .gitignore 或移到仓库外。"
    }

    Write-Host "[2/4] 检查暂存内容..."
    & git diff --cached --check
    if ($LASTEXITCODE -ne 0) {
        Unstage-All
        throw "暂存内容包含空白错误。"
    }

    Write-Host "[3/4] 运行脚本检查和自动测试..."
    & (Join-Path $repoRoot "tools\botc.cmd") check scripts\BOTC.txt
    if ($LASTEXITCODE -ne 0) {
        Unstage-All
        throw "BOTC.txt 检查失败。"
    }
    & (Join-Path $repoRoot "tools\botc.cmd") check scripts\BOTC_test.txt
    if ($LASTEXITCODE -ne 0) {
        Unstage-All
        throw "BOTC_test.txt 检查失败。"
    }
    & (Join-Path $repoRoot "tools\botc.cmd") selftest
    if ($LASTEXITCODE -ne 0) {
        Unstage-All
        throw "自动测试失败。"
    }

    Write-Host "[4/4] 提交并推送..."
    Invoke-Git @("commit", "-m", $message)
    $upstream = & git rev-parse --abbrev-ref --symbolic-full-name "@{u}" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $upstream) {
        Invoke-Git @("push", "-u", "origin", $branch)
    }
    else {
        Invoke-Git @("push")
    }

    Write-Host ""
    Write-Host "上传成功。" -ForegroundColor Green
    Write-Host "分支：$branch"
    Write-Host "提交：$((& git log -1 --oneline))"
}
catch {
    Write-Host ""
    Write-Host "失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    if (-not $NoPause) {
        Write-Host ""
        Read-Host "按 Enter 关闭窗口"
    }
}
