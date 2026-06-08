# refresh-flk-rss.ps1 - 一键刷新 caoyide.com 法律速递 RSS
#
# 用法（PowerShell）：
#   .\scripts\refresh-flk-rss.ps1
#
# 流程：
#   1. 跑 fetch-flk.mjs 抓 flk.npc.gov.cn 最新法规 + 生成 static/flk-rss.xml
#   2. git add / commit / push
#   3. GitHub Actions 自动部署（~1-2 分钟）
#   4. folo 已经订阅 https://caoyide.com/flk-rss.xml，自动看到新内容
#
# 定时跑（每天早上 9 点）：
#   任务计划程序 → 创建任务 → 触发器:每天 09:00
#                    → 操作:启动程序 powershell.exe
#                    → 参数:-ExecutionPolicy Bypass -File "D:\blog\caoyide-blog\scripts\refresh-flk-rss.ps1"
#

# 关键：PowerShell 5.x 调外部命令（git/node）时，任何 stderr 输出都抛 NativeCommandError
# 解决：所有外部命令用 cmd /c 包裹，把 stderr 重定向到 stdout
$ErrorActionPreference = "Continue"  # 不要因为单条命令错误就停
$projectDir = "D:\blog\caoyide-blog"
Set-Location $projectDir

Write-Host "=== 1. 抓取 flk.npc.gov.cn 最新法规 ===" -ForegroundColor Cyan
& cmd /c "node scripts/fetch-flk.mjs 2>&1"
if ($LASTEXITCODE -ne 0) { throw "fetch-flk 失败" }

Write-Host ""
Write-Host "=== 2. git add + commit + push ===" -ForegroundColor Cyan
& cmd /c "git add scripts/fetch-flk.mjs static/flk-rss.xml 2>&1"
& cmd /c "git add scripts/fetch-flk.mjs 2>&1"
& cmd /c "git add static/flk-rss.xml 2>&1"
& cmd /c "git status -sb"

$commitMsg = "chore: 刷新 flk-rss.xml ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))"
& cmd /c "git commit --no-verify -m `"$commitMsg`" 2>&1"
if ($LASTEXITCODE -ne 0) { Write-Host "  (没有改动，无需 commit)" -ForegroundColor Yellow }

& cmd /c "git push 2>&1"
if ($LASTEXITCODE -ne 0) { throw "git push 失败" }

Write-Host ""
Write-Host "=== 3. 等 GitHub Actions 部署 ===" -ForegroundColor Cyan
Write-Host "  约 1-2 分钟部署完成"
Write-Host "  部署后访问: https://caoyide.com/flk-rss.xml"
Write-Host "  folo 订阅会看到新条目（feed id 1146840799258738688）"

Write-Host ""
Write-Host "✅ 完成！" -ForegroundColor Green
