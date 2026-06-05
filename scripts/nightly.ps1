# ===============================================================
#  CLOOP Nightly Batch Wrapper (Stage 4)
#  Com2uS R-Team CLOOP Dashboard
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
    [switch]$DryRun  # Pipeline 만 실행 (commit/push 안 함)
)

$ErrorActionPreference = 'Continue'  # 부분 실패 허용
$startTime = Get-Date

# UTF-8 console (for Korean output)
try { chcp 65001 > $null } catch {}
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# Locate project root regardless of where the script is invoked from
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

# Ensure logs/ exists
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

Write-Log INFO "═══════════════════════════════════════════════════════════"
Write-Log INFO "CLOOP Nightly Batch 시작"
Write-Log INFO "프로젝트 루트: $ProjectRoot"
Write-Log INFO "DryRun 모드: $DryRun"
Write-Log INFO "로그 파일: $LogFile"
Write-Log INFO "═══════════════════════════════════════════════════════════"

# ─── 1. Venv check ──────────────────────────────────────────────
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Write-Log ERROR ".venv 가 없습니다. scripts\setup.ps1 을 먼저 실행하세요."
    exit 1
}
Write-Log INFO "venv Python: $VenvPython"

# ─── 2. Run pipeline ───────────────────────────────────────────
Write-Log INFO ""
Write-Log INFO ">> 단계 1/3: 다중 타이틀 태깅 시작"
$env:PYTHONIOENCODING = 'utf-8'
$pipelineExitCode = 0

# Run and capture both stdout and stderr, append to log
& $VenvPython -m pipeline.main --all-titles 2>&1 | ForEach-Object {
    Write-Host $_
    Add-Content -Path $LogFile -Value $_ -Encoding UTF8
}
$pipelineExitCode = $LASTEXITCODE
Write-Log INFO "파이프라인 종료 코드: $pipelineExitCode"

# ─── 3. Git auto-commit & push (skip if DryRun) ──────────────────
if ($DryRun) {
    Write-Log INFO ""
    Write-Log INFO ">> 단계 2/3: Git auto-push 생략 (DryRun)"
} else {
    Write-Log INFO ""
    Write-Log INFO ">> 단계 2/3: Git auto-commit & push"

    # Check git availability
    $gitCmd = Get-Command git -ErrorAction SilentlyContinue
    if (-not $gitCmd) {
        Write-Log ERROR "git 명령을 찾을 수 없습니다. Git for Windows 설치 필요."
    } else {
        # Verify we're in a git repo
        $isGitRepo = git rev-parse --is-inside-work-tree 2>$null
        if ($LASTEXITCODE -ne 0 -or $isGitRepo -ne 'true') {
            Write-Log WARN "Git 저장소가 아닙니다. commit/push 생략."
        } else {
            # Check for changes in public/data/
            $changes = git status --porcelain public/data 2>&1
            if (-not $changes) {
                Write-Log INFO "public/data 변경 없음 — commit 생략"
            } else {
                Write-Log INFO "변경 감지:"
                $changes | ForEach-Object { Write-Log INFO "  $_" }

                # Add + commit
                git add public/data 2>&1 | Out-Null
                $dateStr = (Get-Date).ToString('yyyy-MM-dd')
                $commitMsg = "auto: nightly tagging $dateStr [pipeline]"
                git commit -m $commitMsg 2>&1 | ForEach-Object {
                    Add-Content -Path $LogFile -Value "  $_" -Encoding UTF8
                }
                if ($LASTEXITCODE -ne 0) {
                    Write-Log WARN "git commit 실패 (변경 없음일 수 있음)"
                } else {
                    Write-Log INFO "Commit 완료: $commitMsg"

                    # Push
                    Write-Log INFO "Push 중..."
                    $pushOutput = git push 2>&1
                    $pushExit = $LASTEXITCODE
                    $pushOutput | ForEach-Object {
                        Write-Log INFO "  push: $_"
                    }
                    if ($pushExit -eq 0) {
                        Write-Log INFO "Push 완료 → GitHub Pages 자동 갱신 예정"
                    } else {
                        Write-Log ERROR "Push 실패 (exit=$pushExit). 인증 또는 네트워크 점검 필요."
                    }
                }
            }
        }
    }
}

# ─── 4. Log rotation (30 days) ─────────────────────────────────
Write-Log INFO ""
Write-Log INFO ">> 단계 3/3: 로그 회전 (30일 초과 삭제)"
$cutoff = (Get-Date).AddDays(-30)
$rotated = 0
Get-ChildItem $LogDir -Filter 'nightly_*.log' -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    ForEach-Object {
        Remove-Item $_.FullName -Force
        $rotated++
    }
Write-Log INFO "오래된 로그 삭제: $rotated 개"

# ─── 5. Summary ─────────────────────────────────────────────────
$duration = (Get-Date) - $startTime
Write-Log INFO ""
Write-Log INFO "═══════════════════════════════════════════════════════════"
Write-Log INFO "CLOOP Nightly Batch 종료"
Write-Log INFO "총 소요: $($duration.TotalSeconds.ToString('F1'))초"
Write-Log INFO "파이프라인 exit: $pipelineExitCode"
Write-Log INFO "로그: $LogFile"
Write-Log INFO "═══════════════════════════════════════════════════════════"

# Task Scheduler 기록용 종료 코드 (0=정상, 1=문제 있음)
exit $pipelineExitCode
