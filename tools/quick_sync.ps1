param(
    [ValidateSet("test", "production")]
    [string]$Mode = "test",
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

function Invoke-Botc {
    param([string[]]$CommandArgs)
    & (Join-Path $repoRoot "tools\botc.cmd") @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "botc 命令失败（退出码 $LASTEXITCODE）"
    }
}

try {
    Write-Host "== BOTC 一键同步与构建 ==" -ForegroundColor Cyan
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "找不到 Git。请先安装 Git。"
    }

    $dirty = @(git status --porcelain)
    if ($dirty.Count -gt 0) {
        Write-Host "检测到未提交的本地修改，为避免覆盖已停止：" -ForegroundColor Yellow
        $dirty | ForEach-Object { Write-Host "  $_" }
        throw "请先提交或处理本地修改，再运行一键同步。"
    }

    Write-Host "[1/5] 切换并更新 main..."
    git switch main
    if ($LASTEXITCODE -ne 0) { throw "切换 main 失败" }
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw "同步 GitHub 失败" }

    Write-Host "[2/5] 检查构建环境..."
    Invoke-Botc @("doctor")
    Invoke-Botc @(
        "check",
        $(if ($Mode -eq "test") { "scripts\BOTC_test.txt" } else { "scripts\BOTC.txt" })
    )

    Write-Host "[3/5] 运行自动测试..."
    Invoke-Botc @("selftest")

    $scriptPath = if ($Mode -eq "test") {
        "scripts\BOTC_test.txt"
    }
    else {
        "scripts\BOTC.txt"
    }
    $prefix = if ($Mode -eq "test") {
        "BOTC_test_sync"
    }
    else {
        "BOTC_sync"
    }
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $documents = [Environment]::GetFolderPath("MyDocuments")
    $outputDir = if ($env:BOTC_SYNC_OUTPUT_DIR) {
        $env:BOTC_SYNC_OUTPUT_DIR
    }
    else {
        Join-Path $documents "StarCraft II\Maps\Test"
    }
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    $output = Join-Path $outputDir "$prefix`_$stamp.SC2Map"

    Write-Host "[4/5] 构建 $Mode 地图..."
    Invoke-Botc @(
        "build",
        "--script", $scriptPath,
        "--out", $output,
        "--split-script"
    )
    Invoke-Botc @("inspect", $output)

    $oldOutputs = @(
        Get-ChildItem -LiteralPath $outputDir -Filter "$prefix`_*.SC2Map" |
            Sort-Object LastWriteTime -Descending |
            Select-Object -Skip 2
    )
    foreach ($oldOutput in $oldOutputs) {
        try {
            [IO.File]::Delete($oldOutput.FullName)
            Write-Host "已清理旧同步地图：$($oldOutput.Name)" -ForegroundColor DarkGray
        }
        catch {
            Write-Host "旧同步地图正被占用，暂未清理：$($oldOutput.Name)" -ForegroundColor Yellow
        }
    }

    Write-Host "[5/5] 完成" -ForegroundColor Green
    Write-Host "测试地图：$output" -ForegroundColor Green
    if (-not $NoPause) {
        Start-Process -FilePath "explorer.exe" -ArgumentList "/select,`"$output`""
    }
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
