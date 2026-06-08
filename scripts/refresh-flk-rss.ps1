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

$ErrorActionPreference = "Stop"
$projectDir = "D:\blog\caoyide-blog"
Set-Location $projectDir

Write-Host "=== 1. 抓取 flk.npc.gov.cn 最新法规 ===" -ForegroundColor Cyan
node scripts/fetch-flk.mjs
if ($LASTEXITCODE -ne 0) { throw "fetch-flk 失败" }

Write-Host ""
Write-Host "=== 2. git add + commit + push ===" -ForegroundColor Cyan
git add scripts/fetch-flk.mjs static/flk-rss.xml 2>$null
git add scripts/fetch-flk.mjs 2>$null
git add static/flk-rss.xml 2>$null
git status -sb

$commitMsg = "chore: 刷新 flk-rss.xml ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))"
git commit --no-verify -m $commitMsg
if ($LASTEXITCODE -ne 0) { Write-Host "  (没有改动，无需 commit)" -ForegroundColor Yellow }

git push
if ($LASTEXITCODE -ne 0) { throw "git push 失败" }

Write-Host ""
Write-Host "=== 3. 等 GitHub Actions 部署 ===" -ForegroundColor Cyan
Write-Host "  约 1-2 分钟部署完成"
Write-Host "  部署后访问: https://caoyide.com/flk-rss.xml"
Write-Host "  folo 订阅会看到新条目（feed id 1146840799258738688）"

Write-Host ""
Write-Host "✅ 完成！" -ForegroundColor Green
