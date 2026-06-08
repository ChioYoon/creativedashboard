# ===============================================================
#  Git Authentication Setup for CLOOP Nightly (Stage 4)
#  Com2uS R-Team
#
#  ASCII-only labels (PowerShell 5.1 cp949 codepage compatibility)
#
#  Usage:
#    .\scripts\setup-git.ps1
# ===============================================================

$ErrorActionPreference = 'Stop'

try { chcp 65001 > $null } catch {}
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Write-Step([string]$Text) { Write-Host "`n>> $Text" -ForegroundColor Cyan }
function Write-OK  ([string]$Text) { Write-Host "   [OK]   $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "   [WARN] $Text" -ForegroundColor Yellow }
function Write-Err ([string]$Text) { Write-Host "   [ERR]  $Text" -ForegroundColor Red }

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
Write-Host "Project root: $ProjectRoot" -ForegroundColor Gray

# --- 1. Git installation check ---
Write-Step "Step 1) Detect Git installation"
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) {
    Write-Err "git command not found."
    Write-Host "   Install Git for Windows: https://git-scm.com/download/win" -ForegroundColor Gray
    Write-Host "   Make sure 'Git Credential Manager' option is checked (default)" -ForegroundColor Gray
    exit 1
}
$gitVersion = git --version
Write-OK "$gitVersion"

# --- 2. Inside a Git repo? ---
Write-Step "Step 2) Check Git repository"
$isRepo = git rev-parse --is-inside-work-tree 2>$null
if ($LASTEXITCODE -ne 0 -or $isRepo -ne 'true') {
    Write-Warn "Current folder is not a Git repository."
    Write-Host "   Check that you cloned from GitHub:" -ForegroundColor Gray
    Write-Host "     git clone https://github.com/chioyoon/creativedashboard.git ." -ForegroundColor White
    Write-Host "   Or add origin remote:" -ForegroundColor Gray
    Write-Host "     git init" -ForegroundColor White
    Write-Host "     git remote add origin https://github.com/chioyoon/creativedashboard.git" -ForegroundColor White
    Write-Host "     git pull origin main" -ForegroundColor White
    exit 1
}
$remoteUrl = git config --get remote.origin.url
if (-not $remoteUrl) {
    Write-Err "Origin remote not configured. Run:"
    Write-Host "     git remote add origin https://github.com/chioyoon/creativedashboard.git" -ForegroundColor White
    exit 1
}
Write-OK "Origin: $remoteUrl"
$currentBranch = git rev-parse --abbrev-ref HEAD
Write-OK "Branch: $currentBranch"

# --- 3. user.name & user.email ---
Write-Step "Step 3) Git user info"
$existingName = git config user.name 2>$null
$existingEmail = git config user.email 2>$null

if ($existingName -and $existingEmail) {
    Write-OK "user.name = $existingName"
    Write-OK "user.email = $existingEmail"
    $modify = Read-Host "Change? (y/N)"
    if ($modify -ne 'y') {
        Write-Host "   (kept existing values)" -ForegroundColor Gray
    } else {
        $existingName = $null
    }
}

if (-not $existingName) {
    $userName = Read-Host "user.name (e.g. 'CLOOP Nightly Bot' or your name)"
    if (-not $userName) { Write-Err "user.name empty"; exit 1 }
    git config user.name $userName
    Write-OK "user.name = $userName"

    $userEmail = Read-Host "user.email (e.g. chioyoon@com2us.com)"
    if (-not $userEmail) { Write-Err "user.email empty"; exit 1 }
    git config user.email $userEmail
    Write-OK "user.email = $userEmail"
}

# --- 4. PAT setup guide ---
Write-Step "Step 4) GitHub Personal Access Token (PAT) setup guide"
Write-Host ""
Write-Host "   1) Visit https://github.com/settings/tokens?type=beta" -ForegroundColor Gray
Write-Host "   2) Click 'Generate new token (fine-grained)'" -ForegroundColor Gray
Write-Host "   3) Token name: 'cloop-nightly-{yourname}'" -ForegroundColor Gray
Write-Host "   4) Expiration: 90 days (or No expiration)" -ForegroundColor Gray
Write-Host "   5) Repository access: 'Only select repositories' -> creativedashboard" -ForegroundColor Gray
Write-Host "   6) Permissions:" -ForegroundColor Gray
Write-Host "      - Contents: Read and write  (required)" -ForegroundColor Gray
Write-Host "      - Metadata: Read-only       (auto-included)" -ForegroundColor Gray
Write-Host "   7) 'Generate token' -> copy the ghp_... value to clipboard" -ForegroundColor Gray
Write-Host "   8) IMPORTANT: copy before closing the page (cannot view again)" -ForegroundColor Gray
Write-Host ""

$readyForPat = Read-Host "PAT generated? (y/N)"
if ($readyForPat -ne 'y') {
    Write-Warn "Generate PAT first, then re-run this script."
    exit 0
}

# --- 5. Credential Manager setup ---
Write-Step "Step 5) Register PAT (Git Credential Manager)"
Write-Host "   First push will prompt 'Sign in to GitHub' dialog:" -ForegroundColor Gray
Write-Host "     - Username: your GitHub login (e.g. chioyoon)" -ForegroundColor Gray
Write-Host "     - Password: paste the PAT you just generated" -ForegroundColor Gray
Write-Host "   Once registered, subsequent pushes are automatic." -ForegroundColor Gray

$credHelper = git config --get credential.helper
if (-not $credHelper) {
    git config --global credential.helper manager
    Write-OK "credential.helper = manager (Git Credential Manager)"
} else {
    Write-OK "credential.helper = $credHelper"
}

# --- 6. Dry-run push test ---
Write-Step "Step 6) Verify push permissions (dry-run, no real changes)"
Write-Host "   Testing ls-remote..." -ForegroundColor Gray
$lsRemote = git ls-remote origin HEAD 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-OK "Remote access OK ($($lsRemote -split '\s+' | Select-Object -First 1))"
} else {
    Write-Err "Remote access failed: $lsRemote"
    Write-Host "   Possible causes:" -ForegroundColor Gray
    Write-Host "     - PAT expired" -ForegroundColor Gray
    Write-Host "     - No repo access permission" -ForegroundColor Gray
    Write-Host "     - Network/firewall block" -ForegroundColor Gray
    exit 1
}

Write-Host "   Testing push --dry-run..." -ForegroundColor Gray
$dryRun = git push --dry-run origin $currentBranch 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-OK "Push permissions OK (dry-run passed)"
} else {
    Write-Warn "Push dry-run result: $dryRun"
    Write-Host "   '[up to date]' is fine. 'rejected' means permission or branch issue." -ForegroundColor Gray
}

# --- 7. Summary ---
Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "Git authentication setup complete" -ForegroundColor Green
Write-Host ""
Write-Host "Next: Email notification setup" -ForegroundColor White
Write-Host "  .\scripts\setup-email.ps1" -ForegroundColor White
Write-Host "=========================================================" -ForegroundColor Green
