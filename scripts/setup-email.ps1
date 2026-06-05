# ===============================================================
#  Email Notification Setup for CLOOP Nightly (Stage 4)
#  Com2uS R-Team
#
#  Purpose:
#    - Configure SMTP credentials in .env
#    - Send a test email to verify the setup
#
#  Supported providers:
#    A. Gmail        (most universal)
#    B. Office 365   (requires SMTP AUTH allowed by IT)
#
#  Usage:
#    .\scripts\setup-email.ps1
#
#  Logs: 실패 시 자동으로 .env 변경 사항 출력
# ===============================================================

$ErrorActionPreference = 'Stop'

# UTF-8 console
try { chcp 65001 > $null } catch {}
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Write-Step([string]$Text) { Write-Host "`n>> $Text" -ForegroundColor Cyan }
function Write-OK  ([string]$Text) { Write-Host "   [OK]   $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "   [WARN] $Text" -ForegroundColor Yellow }
function Write-Err ([string]$Text) { Write-Host "   [ERR]  $Text" -ForegroundColor Red }

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
$EnvPath = Join-Path $ProjectRoot '.env'

if (-not (Test-Path $EnvPath)) {
    Write-Err ".env 파일이 없습니다. setup.ps1 을 먼저 실행하세요."
    exit 1
}

# ─── 1. Provider 선택 ──────────────────────────────────────────
Write-Step "Step 1) 이메일 공급자 선택"
Write-Host @"
   [1] Gmail (개인 Gmail 계정 + 앱 비밀번호)
       - 가장 보편적, 거의 모든 환경에서 작동
       - 2FA 활성화 필요, 앱 비밀번호 발급 필요

   [2] Office 365 (com2us.com 계정)
       - 회사 IT가 SMTP AUTH 허용한 경우만 작동
       - 차단되면 Gmail 사용 권장

   [3] 건너뜀 (SMTP 미설정, 로그 파일만 사용)
"@ -ForegroundColor Gray

$choice = Read-Host "선택 (1/2/3)"

if ($choice -eq '3') {
    Write-Warn "SMTP 미설정 — 야간 배치 결과는 logs/ 디렉토리에만 기록됩니다."
    Write-Host "   로그 확인: Get-ChildItem logs\\nightly_*.log | Sort-Object LastWriteTime -Desc | Select -First 5" -ForegroundColor Gray
    exit 0
}

if ($choice -ne '1' -and $choice -ne '2') {
    Write-Err "올바른 선택지를 입력하세요 (1/2/3)"
    exit 1
}

# ─── 2. 공급자별 안내 ───────────────────────────────────────────
$smtpHost = ""
$smtpPort = "587"
$providerName = ""
$setupHelp = ""

if ($choice -eq '1') {
    $smtpHost = "smtp.gmail.com"
    $providerName = "Gmail"
    $setupHelp = @"
   Gmail 앱 비밀번호 발급 방법:
     1) https://myaccount.google.com/security 접속
     2) '2단계 인증' 활성화 (아직 안 되어 있으면)
     3) https://myaccount.google.com/apppasswords 접속
     4) '앱 이름' 입력: cloop-nightly
     5) '만들기' → 16자 영문 비밀번호 발급 (공백 4개씩 끊어진 형식)
     6) 공백 제거하고 그대로 사용 (예: abcdwxyz1234efgh)
"@
} elseif ($choice -eq '2') {
    $smtpHost = "smtp.office365.com"
    $providerName = "Office 365"
    $setupHelp = @"
   Office 365 안내:
     - SMTP_USER: 본인 com2us 이메일 (예: chioyoon@com2us.com)
     - SMTP_PASSWORD: 본인 com2us 비밀번호
     - 단, IT 정책으로 SMTP AUTH가 차단된 경우 작동 안 함
       (그럴 땐 Gmail 사용 권장)
"@
}

Write-Step "Step 2) $providerName SMTP 설정"
Write-Host $setupHelp -ForegroundColor Gray

# ─── 3. 사용자 입력 ─────────────────────────────────────────────
Write-Step "Step 3) 자격증명 입력"
$smtpUser = Read-Host "SMTP_USER (이메일 주소)"
if (-not $smtpUser) { Write-Err "SMTP_USER 비어있음"; exit 1 }

Write-Host "SMTP_PASSWORD (입력 시 화면에 표시되지 않습니다)"
$securePass = Read-Host -AsSecureString
$smtpPassword = [System.Net.NetworkCredential]::new("", $securePass).Password
if (-not $smtpPassword) { Write-Err "SMTP_PASSWORD 비어있음"; exit 1 }

# Trim Gmail app password spaces (사용자가 공백 포함 붙여넣는 경우 대비)
$smtpPassword = $smtpPassword -replace '\s', ''

$notifyTo = Read-Host "NOTIFY_TO (알림 받을 이메일, 기본: $smtpUser)"
if (-not $notifyTo) { $notifyTo = $smtpUser }

$smtpFrom = $smtpUser  # 보통 동일

# ─── 4. .env 업데이트 ───────────────────────────────────────────
Write-Step "Step 4) .env 파일 업데이트"
$content = [System.IO.File]::ReadAllText($EnvPath, [System.Text.UTF8Encoding]::new($false))

# 각 SMTP_* 줄을 정규식으로 교체
$content = $content -replace '(?m)^SMTP_HOST=.*', "SMTP_HOST=$smtpHost"
$content = $content -replace '(?m)^SMTP_PORT=.*', "SMTP_PORT=$smtpPort"
$content = $content -replace '(?m)^SMTP_USER=.*', "SMTP_USER=$smtpUser"
$content = $content -replace '(?m)^SMTP_PASSWORD=.*', "SMTP_PASSWORD=$smtpPassword"
$content = $content -replace '(?m)^SMTP_FROM=.*', "SMTP_FROM=$smtpFrom"
$content = $content -replace '(?m)^NOTIFY_TO=.*', "NOTIFY_TO=$notifyTo"

[System.IO.File]::WriteAllText($EnvPath, $content, [System.Text.UTF8Encoding]::new($false))
Write-OK ".env 갱신 완료"

# ─── 5. 테스트 메일 발송 ────────────────────────────────────────
Write-Step "Step 5) 테스트 메일 발송"
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Write-Err ".venv 없음. scripts\setup.ps1 먼저 실행."
    exit 1
}

$env:PYTHONIOENCODING = 'utf-8'
& $VenvPython -c "from dotenv import load_dotenv; load_dotenv(); from pipeline.notify import send_test_email; import sys; sys.exit(0 if send_test_email() else 1)"
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-OK "테스트 메일 발송 성공"
    Write-Host "   $notifyTo 받은편지함을 확인하세요." -ForegroundColor Gray
    Write-Host "   제목: '[CLOOP 테스트] SMTP 설정 검증'" -ForegroundColor Gray
} else {
    Write-Err "테스트 메일 발송 실패"
    Write-Host "   가능한 원인:" -ForegroundColor Gray
    if ($choice -eq '1') {
        Write-Host "     - Gmail 앱 비밀번호 오류 (공백 제거 확인)" -ForegroundColor Gray
        Write-Host "     - 2단계 인증 미설정" -ForegroundColor Gray
    } else {
        Write-Host "     - 회사 SMTP AUTH 차단" -ForegroundColor Gray
        Write-Host "     - 비밀번호 오류" -ForegroundColor Gray
    }
    Write-Host "     - 방화벽 차단 (port 587)" -ForegroundColor Gray
    exit 1
}

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "이메일 셋업 완료" -ForegroundColor Green
Write-Host ""
Write-Host "다음 단계: nightly.ps1 수동 테스트 후 Task Scheduler 등록" -ForegroundColor White
Write-Host "  .\scripts\nightly.ps1 -DryRun        # 수동 검증 (git push 생략)" -ForegroundColor White
Write-Host "  .\scripts\register-task.ps1          # Task Scheduler 등록" -ForegroundColor White
Write-Host "=========================================================" -ForegroundColor Green
