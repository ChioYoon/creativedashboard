# ===============================================================
#  CLOOP Nightly Batch Wrapper (Stage 4)
#  Com2uS R-Team CLOOP Dashboard
#
#  ASCII-only labels (PowerShell 5.1 cp949 codepage compatibility)
#
#  Triggered by: Windows Task Scheduler (daily 13:00 KST)
#  Workflow:
#    1. Activate venv
#    2. Run pipeline.main --all-titles
#    3. Git auto-commit & push if public/data/*.json changed
#    4. Notification (handled inside pipeline via notify.py)
#    5. Log rotation (keep last 30 days)
#
#  Manual test:
#    .\scripts\nightly.ps1 [-DryRun]
#
#  Logs: logs/nightly_YYYYMMDD_HHMMSS.log
# ===============================================================

param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Continue'
$startTime = Get-Date

try { chcp 65001 > $null } catch {}
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$LogDir = Join-Path $ProjectRoot 'logs'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$LogFile = Join-Path $LogDir ("nightly_{0:yyyyMMdd_HHmmss}.log" -f $startTime)

function Write-Log {
    param([string]$Level = 'INFO', [string]$Message)
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    $line = "[$ts] [$Level] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

Write-Log INFO "==========================================================="
Write-Log INFO "CLOOP Nightly Batch start"
Write-Log INFO "Project root: $ProjectRoot"
Write-Log INFO "DryRun mode:  $DryRun"
Write-Log INFO "Log file:     $LogFile"
Write-Log INFO "==========================================================="

# --- 1. Venv check ---
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Write-Log ERROR ".venv not found. Run scripts\setup.ps1 first."
    exit 1
}
Write-Log INFO "venv Python: $VenvPython"

# --- 2. Run pipeline ---
Write-Log INFO ""
Write-Log INFO ">> Step 1/3: Multi-title tagging"
$env:PYTHONIOENCODING = 'utf-8'
$pipelineExitCode = 0

& $VenvPython -m pipeline.main --all-titles 2>&1 | ForEach-Object {
    Write-Host $_
    Add-Content -Path $LogFile -Value $_ -Encoding UTF8
}
$pipelineExitCode = $LASTEXITCODE
Write-Log INFO "Pipeline exit code: $pipelineExitCode"

# --- 3. Git auto-commit & push (skip if DryRun) ---
if ($DryRun) {
    Write-Log INFO ""
    Write-Log INFO ">> Step 2/3: Git auto-push skipped (DryRun)"
} else {
    Write-Log INFO ""
    Write-Log INFO ">> Step 2/3: Git auto-commit & push"

    $gitCmd = Get-Command git -ErrorAction SilentlyContinue
    if (-not $gitCmd) {
        Write-Log ERROR "git not found. Install Git for Windows."
    } else {
        $isGitRepo = git rev-parse --is-inside-work-tree 2>$null
        if ($LASTEXITCODE -ne 0 -or $isGitRepo -ne 'true') {
            Write-Log WARN "Not a Git repository. Skipping commit/push."
        } else {
            $changes = git status --porcelain public/data 2>&1
            if (-not $changes) {
                Write-Log INFO "No changes in public/data. Skipping commit."
            } else {
                Write-Log INFO "Detected changes:"
                $changes | ForEach-Object { Write-Log INFO "  $_" }

                git add public/data 2>&1 | Out-Null
                $dateStr = (Get-Date).ToString('yyyy-MM-dd')
                $commitMsg = "auto: nightly tagging $dateStr [pipeline]"
                git commit -m $commitMsg 2>&1 | ForEach-Object {
                    Add-Content -Path $LogFile -Value "  $_" -Encoding UTF8
                }
                if ($LASTEXITCODE -ne 0) {
                    Write-Log WARN "git commit failed (might be no changes)"
                } else {
                    Write-Log INFO "Commit done: $commitMsg"

                    Write-Log INFO "Pushing..."
                    $pushOutput = git push 2>&1
                    $pushExit = $LASTEXITCODE
                    $pushOutput | ForEach-Object {
                        Write-Log INFO "  push: $_"
                    }
                    if ($pushExit -eq 0) {
                        Write-Log INFO "Push done. GitHub Pages will auto-refresh."
                    } else {
                        Write-Log ERROR "Push failed (exit=$pushExit). Check auth or network."
                    }
                }
            }
        }
    }
}

# --- 4. Log rotation (30 days) ---
Write-Log INFO ""
Write-Log INFO ">> Step 3/3: Log rotation (delete logs older than 30 days)"
$cutoff = (Get-Date).AddDays(-30)
$rotated = 0
Get-ChildItem $LogDir -Filter 'nightly_*.log' -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    ForEach-Object {
        Remove-Item $_.FullName -Force
        $rotated++
    }
Write-Log INFO "Old logs deleted: $rotated"

# --- 5. Summary ---
$duration = (Get-Date) - $startTime
Write-Log INFO ""
Write-Log INFO "==========================================================="
Write-Log INFO "CLOOP Nightly Batch end"
Write-Log INFO "Total duration: $($duration.TotalSeconds.ToString('F1')) sec"
Write-Log INFO "Pipeline exit:  $pipelineExitCode"
Write-Log INFO "Log file:       $LogFile"
Write-Log INFO "==========================================================="

exit $pipelineExitCode
