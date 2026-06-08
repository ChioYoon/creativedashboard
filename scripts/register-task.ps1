# ===============================================================
#  Windows Task Scheduler Registration (Stage 4)
#  Com2uS R-Team CLOOP Dashboard
#
#  ASCII-only labels (PowerShell 5.1 cp949 codepage compatibility)
#
#  Usage:
#    .\scripts\register-task.ps1                       # default 13:00
#    .\scripts\register-task.ps1 -Time '08:30'         # change time
#    .\scripts\register-task.ps1 -Unregister           # remove task
#
#  Verify:
#    Get-ScheduledTask -TaskName 'CLOOP-Nightly'
#    Start-ScheduledTask -TaskName 'CLOOP-Nightly'     # run now (test)
# ===============================================================

param(
    [string]$Time = '13:00',
    [switch]$Unregister
)

$ErrorActionPreference = 'Stop'

try { chcp 65001 > $null } catch {}
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Write-Step([string]$Text) { Write-Host "`n>> $Text" -ForegroundColor Cyan }
function Write-OK  ([string]$Text) { Write-Host "   [OK]   $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "   [WARN] $Text" -ForegroundColor Yellow }
function Write-Err ([string]$Text) { Write-Host "   [ERR]  $Text" -ForegroundColor Red }

$TaskName = 'CLOOP-Nightly'
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

# --- Unregister mode ---
if ($Unregister) {
    Write-Step "Unregister Task Scheduler entry"
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-OK "'$TaskName' unregistered"
    } else {
        Write-Warn "'$TaskName' is not registered."
    }
    exit 0
}

# --- Pre-flight checks ---
Write-Step "Step 1) Pre-flight checks"

if ($Time -notmatch '^\d{2}:\d{2}$') {
    Write-Err "Invalid Time format (HH:MM). e.g. '13:00', '08:30'"
    exit 1
}
Write-OK "Schedule time: daily $Time (PC local time)"

$NightlyScript = Join-Path $ProjectRoot 'scripts\nightly.ps1'
if (-not (Test-Path $NightlyScript)) {
    Write-Err "nightly.ps1 not found: $NightlyScript"
    exit 1
}
Write-OK "Nightly script: $NightlyScript"

$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Write-Warn ".venv not found. nightly.ps1 will fail at runtime."
    Write-Host "       Run setup.ps1 first." -ForegroundColor Gray
}

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Warn "'$TaskName' is already registered."
    $overwrite = Read-Host "Overwrite? (y/N)"
    if ($overwrite -ne 'y') {
        Write-Host "   Cancelled. Use -Unregister to remove." -ForegroundColor Gray
        exit 0
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-OK "Existing task removed, re-registering"
}

# --- Build task components ---
Write-Step "Step 2) Build task components"

$psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$action = New-ScheduledTaskAction `
    -Execute $psExe `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$NightlyScript`"" `
    -WorkingDirectory $ProjectRoot
Write-OK "Action: powershell.exe -File nightly.ps1"

$trigger = New-ScheduledTaskTrigger -Daily -At $Time
Write-OK "Trigger: daily at $Time"

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 60) `
    -MultipleInstances IgnoreNew
Write-OK "Settings: StartWhenAvailable, 60-min timeout"

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited
Write-OK "Principal: $env:USERNAME (logon required)"

# --- Register ---
Write-Step "Step 3) Register Task Scheduler"
Register-ScheduledTask `
    -TaskName $TaskName `
    -Description "CLOOP Nightly: Ad creative auto-tagging + GitHub Pages refresh (Com2uS R-Team)" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal | Out-Null

Write-OK "'$TaskName' registered"

# --- Verify ---
Write-Step "Step 4) Verify registration"
$task = Get-ScheduledTask -TaskName $TaskName
$nextRun = (Get-ScheduledTaskInfo -TaskName $TaskName).NextRunTime
Write-OK "State: $($task.State)"
Write-OK "Next run: $nextRun"

# --- Summary ---
Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "Task Scheduler registration complete" -ForegroundColor Green
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor White
Write-Host "  # Run once now (test)" -ForegroundColor Gray
Write-Host "  Start-ScheduledTask -TaskName 'CLOOP-Nightly'" -ForegroundColor White
Write-Host ""
Write-Host "  # Current status" -ForegroundColor Gray
Write-Host "  Get-ScheduledTask -TaskName 'CLOOP-Nightly' | Get-ScheduledTaskInfo" -ForegroundColor White
Write-Host ""
Write-Host "  # Recent log" -ForegroundColor Gray
Write-Host "  Get-ChildItem logs\nightly_*.log | Sort-Object LastWriteTime -Desc | Select -First 1" -ForegroundColor White
Write-Host ""
Write-Host "  # Unregister" -ForegroundColor Gray
Write-Host "  .\scripts\register-task.ps1 -Unregister" -ForegroundColor White
Write-Host ""
Write-Host "Note: PC must be on at $Time for auto-execution." -ForegroundColor Yellow
Write-Host "      If PC was off, it will catch-up on next power-on." -ForegroundColor Yellow
Write-Host "=========================================================" -ForegroundColor Green
