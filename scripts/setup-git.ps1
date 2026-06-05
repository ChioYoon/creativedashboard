# ===============================================================
#  Git Authentication Setup for CLOOP Nightly (Stage 4)
#  Com2uS R-Team
#
#  Purpose:
#    - Verify Git installation
#    - Configure user.name / user.email
#    - Set up HTTPS PAT (Personal Access Token) via Credential Manager
#    - Verify push permissions with a dry-run
#
#  Usage:
#    .\scripts\setup-git.ps1
#
#  Prerequisites:
#    - Git for Windows installed (https://git-scm.com/download/win)
#    - GitHub Personal Access Token (PAT) generated:
#      https://github.com/settings/tokens?type=beta
#      Required scope: 'Contents' (read & write) for this repo only
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
Write-Host "Project root: $ProjectRoot" -ForegroundColor Gray

# ─── 1. Git installation check ──────────────────────────────────
Write-Step "Step 1) Git 설치 확인"
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) {
    Write-Err "git 명령을 찾을 수 없습니다."
    Write-Host "   Git for Windows 설치: https://git-scm.com/download/win" -ForegroundColor Gray
    Write-Host "   설치 시 'Git Credential Manager' 옵션 체크 필수 (기본값)" -ForegroundColor Gray
    exit 1
}
$gitVersion = git --version
Write-OK "$gitVersion"

# ─── 2. Inside a Git repo? ──────────────────────────────────────
Write-Step "Step 2) Git 저장소 확인"
$isRepo = git rev-parse --is-inside-work-tree 2>$null
if ($LASTEXITCODE -ne 0 -or $isRepo -ne 'true') {
    Write-Warn "현재 폴더가 Git 저장소가 아닙니다."
    Write-Host "   기존 GitHub 레포에서 clone 했는지 확인:" -ForegroundColor Gray
    Write-Host "     git clone https://github.com/chioyoon/creativedashboard.git ." -ForegroundColor White
    Write-Host "   또는 origin remote 추가:" -ForegroundColor Gray
    Write-Host "     git init" -ForegroundColor White
    Write-Host "     git remote add origin https://github.com/chioyoon/creativedashboard.git" -ForegroundColor White
    Write-Host "     git pull origin main" -ForegroundColor White
    exit 1
}
$remoteUrl = git config --get remote.origin.url
Write-OK "Origin: $remoteUrl"
$currentBranch = git rev-parse --abbrev-ref HEAD
Write-OK "Branch: $currentBranch"

# ─── 3. user.name & user.email ──────────────────────────────────
Write-Step "Step 3) Git 사용자 정보"
$existingName = git config user.name 2>$null
$existingEmail = git config user.email 2>$null

if ($existingName -and $existingEmail) {
    Write-OK "user.name = $existingName"
    Write-OK "user.email = $existingEmail"
    $modify = Read-Host "변경하시겠습니까? (y/N)"
    if ($modify -ne 'y') {
        Write-Host "   (변경 없이 진행)" -ForegroundColor Gray
    } else {
        $existingName = $null
    }
}

if (-not $existingName) {
    $userName = Read-Host "user.name (예: 'CLOOP Nightly Bot' 또는 본인 이름)"
    if (-not $userName) { Write-Err "user.name 비어있음"; exit 1 }
    git config user.name $userName
    Write-OK "user.name = $userName"

    $userEmail = Read-Host "user.email (예: chioyoon@com2us.com)"
    if (-not $userEmail) { Write-Err "user.email 비어있음"; exit 1 }
    git config user.email $userEmail
    Write-OK "user.email = $userEmail"
}

# ─── 4. PAT 발급 안내 ────────────────────────────────────────────
Write-Step "Step 4) GitHub Personal Access Token (PAT) 발급 안내"
Write-Host @"
   1) https://github.com/settings/tokens?type=beta 접속
   2) 'Generate new token (fine-grained)' 클릭
   3) Token name: 'cloop-nightly-{본인이름}'
   4) Expiration: 90 days (또는 No expiration)
   5) Repository access: 'Only select repositories' → creativedashboard 선택
   6) Permissions:
      - Contents: Read and write  (필수)
      - Metadata: Read-only       (기본 자동 포함)
   7) 'Generate token' → 발급된 ghp_... 토큰을 메모장에 복사
   8) ★ 페이지를 닫기 전에 반드시 복사하세요. 다시 볼 수 없습니다.
"@ -ForegroundColor Gray

$readyForPat = Read-Host "`n   PAT 발급을 완료하셨습니까? (y/N)"
if ($readyForPat -ne 'y') {
    Write-Warn "PAT 발급 후 이 스크립트를 다시 실행하세요."
    exit 0
}

# ─── 5. Credential Manager 등록 ──────────────────────────────────
Write-Step "Step 5) PAT 등록 (Git Credential Manager)"
Write-Host "   Push 테스트로 자격증명을 등록합니다." -ForegroundColor Gray
Write-Host "   첫 push 시 'Sign in to GitHub' 창이 뜨면:" -ForegroundColor Gray
Write-Host "     - Username: GitHub 계정명 (예: chioyoon)" -ForegroundColor Gray
Write-Host "     - Password: 위에서 발급한 PAT 붙여넣기" -ForegroundColor Gray
Write-Host "   한 번 등록되면 다음 push는 자동입니다." -ForegroundColor Gray

# Ensure credential helper is set
$credHelper = git config --get credential.helper
if (-not $credHelper) {
    git config --global credential.helper manager
    Write-OK "credential.helper = manager (Git Credential Manager)"
} else {
    Write-OK "credential.helper = $credHelper"
}

# ─── 6. Dry-run push test ───────────────────────────────────────
Write-Step "Step 6) Push 권한 검증 (dry-run, 실제 변경 없음)"
Write-Host "   ls-remote 로 인증 확인 중..." -ForegroundColor Gray
$lsRemote = git ls-remote origin HEAD 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-OK "원격 접근 정상 ($($lsRemote -split '\s+' | Select-Object -First 1))"
} else {
    Write-Err "원격 접근 실패: $lsRemote"
    Write-Host "   가능한 원인:" -ForegroundColor Gray
    Write-Host "     - PAT 만료" -ForegroundColor Gray
    Write-Host "     - 레포 접근 권한 없음" -ForegroundColor Gray
    Write-Host "     - 네트워크/방화벽 차단" -ForegroundColor Gray
    exit 1
}

# Real push dry-run (creates no commits)
Write-Host "   push --dry-run 으로 실제 push 권한 확인 중..." -ForegroundColor Gray
$dryRun = git push --dry-run origin $currentBranch 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-OK "Push 권한 정상 (dry-run 통과)"
} else {
    Write-Warn "Push dry-run 결과: $dryRun"
    Write-Host "   '[up to date]' 메시지면 정상. 'rejected'면 권한 또는 분기 문제." -ForegroundColor Gray
}

# ─── 7. Summary ──────────────────────────────────────────────────
Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "Git 인증 셋업 완료" -ForegroundColor Green
Write-Host ""
Write-Host "다음 단계: 이메일 알림 셋업" -ForegroundColor White
Write-Host "  .\scripts\setup-email.ps1" -ForegroundColor White
Write-Host "=========================================================" -ForegroundColor Green
