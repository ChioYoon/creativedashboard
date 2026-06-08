# ===============================================================
#  Google Ads OAuth Setup Wizard (Stage 5-A)
#  Com2uS R-Team CLOOP Dashboard
#
#  ASCII-only labels (PowerShell 5.1 cp949 codepage compatibility)
#
#  Purpose:
#    - Interactive OAuth refresh token generation
#    - Auto-create .secrets/google_ads.yaml
#    - Run healthcheck to verify
#
#  Prerequisites (Stage 5-A):
#    1. Com2uS ENT GCP OAuth Desktop Client ID issued (IT ticket approved)
#    2. Google Ads Developer Token in hand
#    3. MCC (login_customer_id) and target customer_id known
#
#  Usage:
#    .\scripts\setup-google-ads.ps1
#    .\scripts\setup-google-ads.ps1 -Healthcheck       # Skip OAuth, only verify
#    .\scripts\setup-google-ads.ps1 -Reset             # Delete existing yaml
# ===============================================================

param(
    [switch]$Healthcheck,
    [switch]$Reset
)

$ErrorActionPreference = 'Stop'

try { chcp 65001 > $null } catch {}
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Write-Step([string]$Text) { Write-Host "`n>> $Text" -ForegroundColor Cyan }
function Write-OK  ([string]$Text) { Write-Host "   [OK]   $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "   [WARN] $Text" -ForegroundColor Yellow }
function Write-Err ([string]$Text) { Write-Host "   [ERR]  $Text" -ForegroundColor Red }

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
$SecretsDir = Join-Path $ProjectRoot '.secrets'
$YamlPath = Join-Path $SecretsDir 'google_ads.yaml'
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

# ─── Reset mode ────────────────────────────────────────────────
if ($Reset) {
    Write-Step "Reset mode — remove existing google_ads.yaml"
    if (Test-Path $YamlPath) {
        Remove-Item $YamlPath -Force
        Write-OK "Removed $YamlPath"
    } else {
        Write-Warn "No file to remove."
    }
    exit 0
}

# ─── Healthcheck mode ──────────────────────────────────────────
if ($Healthcheck) {
    Write-Step "Healthcheck — verify Google Ads OAuth auth"
    if (-not (Test-Path $YamlPath)) {
        Write-Err "google_ads.yaml not found at $YamlPath"
        Write-Host "       Run .\scripts\setup-google-ads.ps1 (without -Healthcheck) to generate." -ForegroundColor Gray
        exit 1
    }
    if (-not (Test-Path $VenvPython)) {
        Write-Err ".venv not found. Run scripts\setup.ps1 first."
        exit 1
    }
    $env:PYTHONIOENCODING = 'utf-8'
    & $VenvPython -m pipeline.kpi --healthcheck
    exit $LASTEXITCODE
}

# ─── Pre-flight checks ─────────────────────────────────────────
Write-Step "Step 1) Pre-flight checks"

if (-not (Test-Path $VenvPython)) {
    Write-Err ".venv not found. Run scripts\setup.ps1 first."
    exit 1
}
Write-OK "venv Python: $VenvPython"

# google-ads SDK installation (idempotent — pip skips if already satisfied)
# NOTE: PS 5.1 bug — `python -c "import ..." 2>&1` under ErrorActionPreference=Stop
#       wraps stderr Tracebacks as NativeCommandError and aborts the script
#       BEFORE the install branch runs. We bypass by always calling pip install;
#       pip is fast & idempotent when requirement is already satisfied.
Write-Host "   Ensuring google-ads SDK installed..." -ForegroundColor Gray
$env:PYTHONIOENCODING = 'utf-8'
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $VenvPython -m pip install --quiet --disable-pip-version-check 'google-ads>=28.2.0,<32.0.0'
$pipExit = $LASTEXITCODE
$ErrorActionPreference = $prevEAP
if ($pipExit -ne 0) {
    Write-Err "pip install google-ads failed (exit $pipExit). Re-running verbose to show details:"
    & $VenvPython -m pip install 'google-ads>=28.2.0,<32.0.0'
    exit 1
}
Write-OK "google-ads SDK ready"

# Existing yaml check
if (Test-Path $YamlPath) {
    Write-Warn "Existing google_ads.yaml found at $YamlPath"
    $overwrite = Read-Host "Overwrite? (y/N)"
    if ($overwrite -ne 'y') {
        Write-Host "   Cancelled. Use -Healthcheck to verify existing auth." -ForegroundColor Gray
        exit 0
    }
}

# ─── Collect credentials ───────────────────────────────────────
Write-Step "Step 2) Enter Google Ads credentials"

Write-Host "   Get from Com2uS ENT GCP (OAuth Client ID, Desktop type):" -ForegroundColor Gray
$clientId = Read-Host "OAuth client_id (e.g. 1234567890.apps.googleusercontent.com)"
if (-not $clientId) { Write-Err "client_id empty"; exit 1 }

Write-Host "OAuth client_secret (input is hidden):" -ForegroundColor Gray
$secureClientSecret = Read-Host -AsSecureString
$clientSecret = [System.Net.NetworkCredential]::new("", $secureClientSecret).Password
if (-not $clientSecret) { Write-Err "client_secret empty"; exit 1 }

Write-Host "Developer Token (from Google Ads > Tools > API Center, input is hidden):" -ForegroundColor Gray
$secureDevToken = Read-Host -AsSecureString
$devToken = [System.Net.NetworkCredential]::new("", $secureDevToken).Password
if (-not $devToken) { Write-Err "developer_token empty"; exit 1 }

Write-Host "   Manager Account (MCC) customer ID (10 digits, no hyphens):" -ForegroundColor Gray
$loginCustomerId = Read-Host "login_customer_id"
$loginCustomerId = $loginCustomerId -replace '-', '' -replace '\s', ''
if (-not $loginCustomerId -or $loginCustomerId.Length -ne 10) {
    Write-Err "login_customer_id must be exactly 10 digits"
    exit 1
}

# ─── OAuth refresh token flow ──────────────────────────────────
Write-Step "Step 3) OAuth refresh token generation (browser flow)"
Write-Host "   A browser window will open. Sign in with your Com2uS Google account" -ForegroundColor Gray
Write-Host "   that has access to Google Ads, then approve the requested permissions." -ForegroundColor Gray
Write-Host ""
Write-Host "   If the browser does not open automatically, copy the printed URL." -ForegroundColor Gray
Write-Host ""
Write-Host "   Press Enter to start..." -ForegroundColor White
[void](Read-Host)

# Use Python helper to run InstalledAppFlow
$flowScript = @"
import sys
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print('ERR_NO_OAUTHLIB', flush=True)
    sys.exit(2)

CLIENT_CONFIG = {
    'installed': {
        'client_id':     '$clientId',
        'client_secret': '$clientSecret',
        'auth_uri':      'https://accounts.google.com/o/oauth2/auth',
        'token_uri':     'https://oauth2.googleapis.com/token',
        'redirect_uris': ['http://localhost:8080/'],
    }
}
SCOPES = ['https://www.googleapis.com/auth/adwords']

try:
    flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    creds = flow.run_local_server(host='localhost', port=8080, open_browser=True)
    print('REFRESH_TOKEN:' + creds.refresh_token, flush=True)
except Exception as e:
    print(f'ERR:{type(e).__name__}:{e}', flush=True)
    sys.exit(3)
"@

# Ensure google-auth-oauthlib installed (idempotent install — same PS 5.1 stderr workaround as above)
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $VenvPython -m pip install --quiet --disable-pip-version-check 'google-auth-oauthlib>=1.2.0,<2.0.0'
$pipExit = $LASTEXITCODE
$ErrorActionPreference = $prevEAP
if ($pipExit -ne 0) {
    Write-Err "pip install google-auth-oauthlib failed (exit $pipExit). Re-running verbose:"
    & $VenvPython -m pip install 'google-auth-oauthlib>=1.2.0,<2.0.0'
    exit 1
}

# Run flow
$tempScript = Join-Path $env:TEMP "cloop_oauth_flow_$([guid]::NewGuid().ToString().Substring(0,8)).py"
Set-Content -Path $tempScript -Value $flowScript -Encoding UTF8

$flowOutput = & $VenvPython $tempScript 2>&1
Remove-Item $tempScript -Force -ErrorAction SilentlyContinue

if ($flowOutput -is [array]) {
    $flowOutput = $flowOutput -join "`n"
}
$flowOutput = [string]$flowOutput

if ($flowOutput -match 'REFRESH_TOKEN:(\S+)') {
    $refreshToken = $matches[1]
    Write-OK "Refresh token generated (length=$($refreshToken.Length))"
} else {
    Write-Err "OAuth flow failed:"
    Write-Host $flowOutput -ForegroundColor Gray
    Write-Host "" -ForegroundColor Gray
    Write-Host "   Common issues:" -ForegroundColor Gray
    Write-Host "     - 'access_blocked' : OAuth consent screen not set to Internal" -ForegroundColor Gray
    Write-Host "     - 'redirect_uri_mismatch' : Add http://localhost:8080/ to client redirect URIs" -ForegroundColor Gray
    Write-Host "     - port 8080 in use: close other apps using that port" -ForegroundColor Gray
    exit 1
}

# ─── Write yaml ─────────────────────────────────────────────────
Write-Step "Step 4) Write .secrets/google_ads.yaml"

if (-not (Test-Path $SecretsDir)) {
    New-Item -ItemType Directory -Path $SecretsDir | Out-Null
}

$yaml = @"
# CLOOP Google Ads API credentials — gitignored
# Generated by scripts/setup-google-ads.ps1 on $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
# DO NOT COMMIT this file. .gitignore excludes the .secrets/ directory.

developer_token: $devToken
client_id: $clientId
client_secret: $clientSecret
refresh_token: $refreshToken
login_customer_id: '$loginCustomerId'
use_proto_plus: true
"@

[System.IO.File]::WriteAllText($YamlPath, $yaml, [System.Text.UTF8Encoding]::new($false))
Write-OK "Wrote $YamlPath"

# ─── Update .env ────────────────────────────────────────────────
Write-Step "Step 5) Update .env"
$envPath = Join-Path $ProjectRoot '.env'
if (-not (Test-Path $envPath)) {
    Write-Warn ".env not found, creating from template..."
    Copy-Item (Join-Path $ProjectRoot '.env.example') $envPath
}

$envContent = [System.IO.File]::ReadAllText($envPath, [System.Text.UTF8Encoding]::new($false))
if ($envContent -notmatch '(?m)^GOOGLE_ADS_CONFIG_PATH=') {
    Add-Content -Path $envPath -Value "`n# Stage 5 Google Ads API" -Encoding UTF8
    Add-Content -Path $envPath -Value "GOOGLE_ADS_CONFIG_PATH=.secrets/google_ads.yaml" -Encoding UTF8
    Add-Content -Path $envPath -Value "GOOGLE_ADS_KPI_WINDOW_DAYS=28" -Encoding UTF8
    Write-OK ".env updated with GOOGLE_ADS_CONFIG_PATH"
} else {
    Write-OK ".env already has GOOGLE_ADS_CONFIG_PATH"
}

# ─── Healthcheck ─────────────────────────────────────────────────
Write-Step "Step 6) Healthcheck"
& $VenvPython -m pipeline.kpi --healthcheck
$healthExit = $LASTEXITCODE

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
if ($healthExit -eq 0) {
    Write-Host "Google Ads OAuth setup complete" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host "  1. Update js/titles.json with _pipeline_google_ads_customer_id" -ForegroundColor White
    Write-Host "  2. Test fetch: python -m pipeline.kpi --title pepp-us --days 3 --limit 5" -ForegroundColor White
    Write-Host "  3. Full run: python -m pipeline.main --all-titles" -ForegroundColor White
} else {
    Write-Host "Setup complete but healthcheck failed" -ForegroundColor Yellow
    Write-Host "Check the error above and retry: .\scripts\setup-google-ads.ps1 -Healthcheck" -ForegroundColor Gray
}
Write-Host "=========================================================" -ForegroundColor Green

exit $healthExit
