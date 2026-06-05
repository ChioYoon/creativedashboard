# ===============================================================
#  Windows Task Scheduler Registration (Stage 4)
#  Com2uS R-Team CLOOP Dashboard
#
#  Purpose:
#    Register a daily Task Scheduler entry that runs nightly.ps1
#
#  Schedule:
#    Daily at 13:00 KST (user's local time)
#    Runs whether user is logged on or not (requires saved credentials)
#
#  Usage:
#    .\scripts\register-task.ps1                       # 13:00 기본
#    .\scripts\register-task.ps1 -Time '08:30'         # 시간 변경
#    .\scripts\register-task.ps1 -Unregister           # 등록 해제
#
#  Verify:
#    Get-ScheduledTask -TaskName 'CLOOP-Nightly'
#    Start-ScheduledTask -TaskName 'CLOOP-Nightly'     # 즉시 실행 테스트
# ===============================================================

param(
    [string]$Time = '13:00',     # HH:MM 24-hour format (local time)
    [switch]$Unregister          # Remove task instead of creating
)

$ErrorActionPreference = 'Stop'

# UTF-8 console
try { chcp 65001 > $null } catch {}
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Write-Step([string]$Text) { Write-Host "`n>> $Text" -ForegroundColor Cyan }
function Write-OK  ([string]$Text) { Write-Host "   [OK]   $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "   [WARN] $Text" -ForegroundColor Yellow }
function Write-Err ([string]$Text) { Write-Host "   [ERR]  $Text" -ForegroundColor Red }

$TaskName = 'CLOOP-Nightly'
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

# ─── Unregister mode ────────────────────────────────────────────
if ($Unregister) {
    Write-Step "Task Scheduler 등록 해제"
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-OK "'$TaskName' 등록 해제 완료"
    } else {
        Write-Warn "'$TaskName' 등록되어 있지 않습니다."
    }
    exit 0
}

# ─── Pre-flight checks ──────────────────────────────────────────
Write-Step "Step 1) 사전 검증"

# Time format
if ($Time -notmatch '^\d{2}:\d{2}$') {
    Write-Err "Time 형식 오류 (HH:MM 형식). 예: '13:00', '08:30'"
    exit 1
}
Write-OK "실행 시각: 매일 $Time (PC 로컬 시각)"

# Script paths
$NightlyScript = Join-Path $ProjectRoot 'scripts\nightly.ps1'
if (-not (Test-Path $NightlyScript)) {
    Write-Err "nightly.ps1 을 찾을 수 없습니다: $NightlyScript"
    exit 1
}
Write-OK "Nightly 스크립트: $NightlyScript"

# Venv
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Write-Warn ".venv 가 없습니다. nightly.ps1 실행 시 실패할 것입니다."
    Write-Host "       먼저 setup.ps1 을 실행하세요." -ForegroundColor Gray
}

# Existing task?
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Warn "'$TaskName' 이 이미 등록되어 있습니다."
    $overwrite = Read-Host "덮어쓰시겠습니까? (y/N)"
    if ($overwrite -ne 'y') {
        Write-Host "   취소되었습니다. 등록 해제하려면 -Unregister 옵션 사용." -ForegroundColor Gray
        exit 0
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-OK "기존 task 해제 완료, 새로 등록 진행"
}

# ─── Build task components ──────────────────────────────────────
Write-Step "Step 2) Task 구성 정의"

# Action: PowerShell 실행 (정책 우회 + nightly.ps1)
$psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$action = New-ScheduledTaskAction `
    -Execute $psExe `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$NightlyScript`"" `
    -WorkingDirectory $ProjectRoot
Write-OK "Action: powershell.exe -File nightly.ps1"

# Trigger: 매일 지정 시간
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
Write-OK "Trigger: 매일 $Time"

# Settings: 부팅 직후 못 실행했으면 가능한 빨리 실행, 60분 limit
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 60) `
    -MultipleInstances IgnoreNew
Write-OK "Settings: PC가 일시 OFF 상태였으면 다음 ON 시점에 catch-up, 60분 timeout"

# Principal: 현재 로그인 사용자
$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited
Write-OK "Principal: $env:USERNAME (로그인 시에만 실행)"

# ─── Register ───────────────────────────────────────────────────
Write-Step "Step 3) Task Scheduler 등록"
Register-ScheduledTask `
    -TaskName $TaskName `
    -Description "CLOOP Nightly: 광고 소재 자동 태깅 + GitHub Pages 갱신 (Com2uS R-Team)" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal | Out-Null

Write-OK "'$TaskName' 등록 완료"

# ─── Verify ─────────────────────────────────────────────────────
Write-Step "Step 4) 등록 검증"
$task = Get-ScheduledTask -TaskName $TaskName
$nextRun = (Get-ScheduledTaskInfo -TaskName $TaskName).NextRunTime
Write-OK "상태: $($task.State)"
Write-OK "다음 실행 예정: $nextRun"

# ─── Summary ────────────────────────────────────────────────────
Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "Task Scheduler 등록 완료" -ForegroundColor Green
Write-Host ""
Write-Host "유용한 명령:" -ForegroundColor White
Write-Host "  # 즉시 1회 실행 (테스트)" -ForegroundColor Gray
Write-Host "  Start-ScheduledTask -TaskName 'CLOOP-Nightly'" -ForegroundColor White
Write-Host ""
Write-Host "  # 현재 상태 조회" -ForegroundColor Gray
Write-Host "  Get-ScheduledTask -TaskName 'CLOOP-Nightly' | Get-ScheduledTaskInfo" -ForegroundColor White
Write-Host ""
Write-Host "  # 최근 로그 확인" -ForegroundColor Gray
Write-Host "  Get-ChildItem logs\nightly_*.log | Sort-Object LastWriteTime -Desc | Select -First 1" -ForegroundColor White
Write-Host ""
Write-Host "  # 등록 해제" -ForegroundColor Gray
Write-Host "  .\scripts\register-task.ps1 -Unregister" -ForegroundColor White
Write-Host ""
Write-Host "주의: PC가 매일 $Time 에 켜져 있어야 자동 실행됩니다." -ForegroundColor Yellow
Write-Host "      OFF 상태였다면 다음 ON 시점에 자동 catch-up." -ForegroundColor Yellow
Write-Host "=========================================================" -ForegroundColor Green
