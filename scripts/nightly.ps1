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
# Any git-step failure (commit/pull/push) -> exit 2, so Task Scheduler
# "Last Run Result" is non-zero. 2026-09-23..29 push was rejected 7 days
# while the scheduler showed success.
$gitFailed = $false

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
        $gitFailed = $true
    } else {
        $isGitRepo = git rev-parse --is-inside-work-tree 2>$null
        if ($LASTEXITCODE -ne 0 -or $isGitRepo -ne 'true') {
            Write-Log WARN "Not a Git repository. Skipping commit/push."
        } else {
            # Brief mirror (js/brand_briefs.json, js/gate_registry.json) is rewritten by the
            # pipeline (sync_mirror); without committing it the live gate never updates.
            $AutoPaths = @('public/data', 'js/brand_briefs.json', 'js/gate_registry.json')
            $changes = git status --porcelain -- $AutoPaths 2>&1
            if (-not $changes) {
                Write-Log INFO "No changes in pipeline outputs. Skipping commit."
            } else {
                Write-Log INFO "Detected changes:"
                $changes | ForEach-Object { Write-Log INFO "  $_" }

                git add -- $AutoPaths 2>&1 | Out-Null
                $dateStr = (Get-Date).ToString('yyyy-MM-dd')
                $commitMsg = "auto: nightly tagging $dateStr [pipeline]"
                # Pathspec-limited: never sweep up anything else a dev left staged.
                git commit -m $commitMsg -- $AutoPaths 2>&1 | ForEach-Object {
                    Add-Content -Path $LogFile -Value "  $_" -Encoding UTF8
                }
                if ($LASTEXITCODE -ne 0) {
                    # public/data had changes, so a commit failure is real (hook, identity, lock)
                    Write-Log ERROR "git commit failed (exit=$LASTEXITCODE). See commit output above."
                    $gitFailed = $true
                } else {
                    Write-Log INFO "Commit done: $commitMsg"

                    # Sync before push: a web merge / other-session push makes the remote
                    # ahead and push is rejected as non-fast-forward (2026-09 incident).
                    # Only pipeline outputs are committed, so usually conflict-free. On conflict:
                    # abort rebase and skip push (manual reconcile).
                    # --autostash: uncommitted edits elsewhere in the checkout (dev work,
                    # brief mirror sync) otherwise make pull refuse -> push skipped
                    # (2026-10-07..12 incident).
                    Write-Log INFO "Syncing with remote (pull --rebase --autostash origin main)..."
                    $pullOutput = git pull --rebase --autostash origin main 2>&1
                    $pullExit = $LASTEXITCODE
                    $pullOutput | ForEach-Object { Write-Log INFO "  pull: $_" }
                    if ($pullExit -ne 0) {
                        Write-Log ERROR "pull --rebase failed (exit=$pullExit). Aborting rebase, skipping push. Manual reconcile needed."
                        git rebase --abort 2>&1 | ForEach-Object { Write-Log INFO "  rebase-abort: $_" }
                        $gitFailed = $true
                    } else {
                        Write-Log INFO "Pushing..."
                        $pushOutput = git push 2>&1
                        $pushExit = $LASTEXITCODE
                        $pushOutput | ForEach-Object {
                            Write-Log INFO "  push: $_"
                        }
                        if ($pushExit -eq 0) {
                            Write-Log INFO "Push done. GitHub Pages will auto-refresh."
                        } else {
                            Write-Log ERROR "Push failed (exit=$pushExit). Reason is in the 'push:' lines above."
                            $gitFailed = $true
                        }
                    }
                }
            }
        }
    }
}

# --- BigQuery export (after git push; isolated; gating lives in Python) ---
if (-not $DryRun) {
    Write-Log INFO "BigQuery export start"
    & $VenvPython -m pipeline.bq_export --all-titles 2>&1 | ForEach-Object { Write-Log INFO $_ }
    if ($LASTEXITCODE -ne 0) { Write-Log WARN "bq_export exited abnormally (no effect on dashboard/git)" }
} else {
    Write-Log INFO "DryRun - BigQuery export skipped"
}

# --- Google Sheets export (BI portal; after git push; isolated; gating lives in Python) ---
if (-not $DryRun) {
    Write-Log INFO "Sheets export start"
    & $VenvPython -m pipeline.sheets_export 2>&1 | ForEach-Object { Write-Log INFO $_ }
    if ($LASTEXITCODE -ne 0) { Write-Log WARN "sheets_export failed (no effect on dashboard/git; previous sheet kept or partially replaced)" }
} else {
    Write-Log INFO "DryRun - Sheets export skipped"
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
Write-Log INFO "Git failed:     $gitFailed"
Write-Log INFO "Log file:       $LogFile"
Write-Log INFO "==========================================================="

# Pipeline failure keeps its own code; git-only failure -> 2.
if ($pipelineExitCode -ne 0) { exit $pipelineExitCode }
if ($gitFailed) { exit 2 }
exit 0
