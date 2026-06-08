# ===============================================================
#  Email Notification Setup for CLOOP Nightly (Stage 4)
#  Com2uS R-Team
#
#  ASCII-only labels (PowerShell 5.1 cp949 codepage compatibility)
#
#  Purpose:
#    - Configure SMTP credentials in .env
#    - Send a test email to verify the setup
#
#  Usage:
#    .\scripts\setup-email.ps1
# ===============================================================

$ErrorActionPreference = 'Stop'

try { chcp 65001 > $null } catch {}
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Write-Step([string]$Text) { Write-Host "`n>> $Text" -ForegroundColor Cyan }
function Write-OK  ([string]$Text) { Write-Host "   [OK]   $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "   [WARN] $Text" -ForegroundColor Yellow }
function Write-Err ([string]$Text) { Write-Host "   [ERR]  $Text" -ForegroundColor Red }

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
$EnvPath = Join-Path $ProjectRoot '.env'

if (-not (Test-Path $EnvPath)) {
    Write-Err ".env file not found. Run setup.ps1 first."
    exit 1
}

# --- 1. Provider choice ---
Write-Step "Step 1) Select email provider"
Write-Host ""
Write-Host "   [1] Gmail (personal Gmail + app password)"           -ForegroundColor Gray
Write-Host "       - Most universal, works almost everywhere"       -ForegroundColor Gray
Write-Host "       - Requires 2FA enabled + app password generation" -ForegroundColor Gray
Write-Host ""
Write-Host "   [2] Office 365 (com2us.com account)"                 -ForegroundColor Gray
Write-Host "       - Only works if IT allowed SMTP AUTH"            -ForegroundColor Gray
Write-Host "       - If blocked, use Gmail instead"                 -ForegroundColor Gray
Write-Host ""
Write-Host "   [3] Skip (no SMTP, log files only)"                  -ForegroundColor Gray
Write-Host ""

$choice = Read-Host "Choice (1/2/3)"

if ($choice -eq '3') {
    Write-Warn "SMTP not configured. Nightly results will be written to logs/ only."
    Write-Host "   View logs: Get-ChildItem logs\nightly_*.log | Sort-Object LastWriteTime -Desc | Select -First 5" -ForegroundColor Gray
    exit 0
}

if ($choice -ne '1' -and $choice -ne '2') {
    Write-Err "Invalid choice (1/2/3 only)"
    exit 1
}

# --- 2. Provider guidance ---
$smtpHost = ""
$smtpPort = "587"
$providerName = ""

if ($choice -eq '1') {
    $smtpHost = "smtp.gmail.com"
    $providerName = "Gmail"

    Write-Step "Step 2) Gmail SMTP configuration"
    Write-Host "   Gmail app password setup:" -ForegroundColor Gray
    Write-Host "     1) Visit https://myaccount.google.com/security" -ForegroundColor Gray
    Write-Host "     2) Enable 2-Step Verification (if not already)" -ForegroundColor Gray
    Write-Host "     3) Visit https://myaccount.google.com/apppasswords" -ForegroundColor Gray
    Write-Host "     4) App name: cloop-nightly" -ForegroundColor Gray
    Write-Host "     5) Click 'Create' - 16-char password is generated" -ForegroundColor Gray
    Write-Host "     6) Format: 4 groups of 4 chars (spaces stripped automatically)" -ForegroundColor Gray
} elseif ($choice -eq '2') {
    $smtpHost = "smtp.office365.com"
    $providerName = "Office 365"

    Write-Step "Step 2) Office 365 SMTP configuration"
    Write-Host "   Office 365 notes:" -ForegroundColor Gray
    Write-Host "     - SMTP_USER: your com2us email (e.g., chioyoon@com2us.com)" -ForegroundColor Gray
    Write-Host "     - SMTP_PASSWORD: your com2us account password" -ForegroundColor Gray
    Write-Host "     - May fail if IT policy blocks SMTP AUTH (try Gmail then)" -ForegroundColor Gray
}

# --- 3. User input ---
Write-Step "Step 3) Enter credentials"
$smtpUser = Read-Host "SMTP_USER (email address)"
if (-not $smtpUser) { Write-Err "SMTP_USER cannot be empty"; exit 1 }

Write-Host "SMTP_PASSWORD (input is hidden):"
$securePass = Read-Host -AsSecureString
$smtpPassword = [System.Net.NetworkCredential]::new("", $securePass).Password
if (-not $smtpPassword) { Write-Err "SMTP_PASSWORD cannot be empty"; exit 1 }

# Trim Gmail app password spaces (paste-friendly)
$smtpPassword = $smtpPassword -replace '\s', ''

$notifyTo = Read-Host "NOTIFY_TO (recipient, default: $smtpUser)"
if (-not $notifyTo) { $notifyTo = $smtpUser }

$smtpFrom = $smtpUser

# --- 4. Update .env ---
Write-Step "Step 4) Update .env file"
$content = [System.IO.File]::ReadAllText($EnvPath, [System.Text.UTF8Encoding]::new($false))

$content = $content -replace '(?m)^SMTP_HOST=.*', "SMTP_HOST=$smtpHost"
$content = $content -replace '(?m)^SMTP_PORT=.*', "SMTP_PORT=$smtpPort"
$content = $content -replace '(?m)^SMTP_USER=.*', "SMTP_USER=$smtpUser"
$content = $content -replace '(?m)^SMTP_PASSWORD=.*', "SMTP_PASSWORD=$smtpPassword"
$content = $content -replace '(?m)^SMTP_FROM=.*', "SMTP_FROM=$smtpFrom"
$content = $content -replace '(?m)^NOTIFY_TO=.*', "NOTIFY_TO=$notifyTo"

[System.IO.File]::WriteAllText($EnvPath, $content, [System.Text.UTF8Encoding]::new($false))
Write-OK ".env updated"

# --- 5. Send test email ---
Write-Step "Step 5) Send test email"
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Write-Err ".venv not found. Run scripts\setup.ps1 first."
    exit 1
}

$env:PYTHONIOENCODING = 'utf-8'
& $VenvPython -c "from dotenv import load_dotenv; load_dotenv(); from pipeline.notify import send_test_email; import sys; sys.exit(0 if send_test_email() else 1)"
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-OK "Test email sent successfully"
    Write-Host "   Check inbox at: $notifyTo" -ForegroundColor Gray
    Write-Host "   Subject: '[CLOOP TEST] SMTP setup verification'" -ForegroundColor Gray
} else {
    Write-Err "Test email failed"
    Write-Host "   Possible causes:" -ForegroundColor Gray
    if ($choice -eq '1') {
        Write-Host "     - Wrong Gmail app password (check spaces stripped)" -ForegroundColor Gray
        Write-Host "     - 2-Step Verification not enabled" -ForegroundColor Gray
    } else {
        Write-Host "     - Company IT blocked SMTP AUTH" -ForegroundColor Gray
        Write-Host "     - Wrong password" -ForegroundColor Gray
    }
    Write-Host "     - Firewall blocking port 587" -ForegroundColor Gray
    exit 1
}

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "Email setup complete" -ForegroundColor Green
Write-Host ""
Write-Host "Next: Test nightly batch manually, then register Task Scheduler" -ForegroundColor White
Write-Host "  .\scripts\nightly.ps1 -DryRun        # Verify (no git push)" -ForegroundColor White
Write-Host "  .\scripts\register-task.ps1          # Register Task Scheduler" -ForegroundColor White
Write-Host "=========================================================" -ForegroundColor Green
