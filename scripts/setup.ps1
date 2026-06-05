# ===============================================================
#  Stage 2 MVP - One-Click Python Setup (PowerShell)
#  Com2uS R-Team CLOOP Dashboard
#
#  Usage:
#    Run from project root:
#      .\scripts\setup.ps1
#
#  Steps:
#    1. Check Python 3.11+
#    2. Create .venv virtual environment
#    3. Upgrade pip + install dependencies
#    4. Copy .env template (if missing)
#    5. Dry-run scan (no Gemini calls)
#
#  NOTE: This script uses ASCII-only labels to avoid PowerShell 5.1
#  encoding issues. The Python output (in step 5) preserves Korean.
# ===============================================================

$ErrorActionPreference = 'Stop'

# Force UTF-8 console codepage so Python stdout (Korean) renders correctly.
try { chcp 65001 > $null } catch {}
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# --- color helpers ---
function Write-Step([string]$Text) { Write-Host "`n>> $Text" -ForegroundColor Cyan }
function Write-OK  ([string]$Text) { Write-Host "   [OK]   $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "   [WARN] $Text" -ForegroundColor Yellow }
function Write-Err ([string]$Text) { Write-Host "   [ERR]  $Text" -ForegroundColor Red }

# Move to project root regardless of where the script was invoked from.
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot
Write-Host "Project root: $ProjectRoot" -ForegroundColor Gray

# --- 1. Detect Python 3.11+ ---
Write-Step "Step 1) Detect Python 3.11+"
$pythonCmd = $null
foreach ($cmd in @('py', 'python', 'python3')) {
    try {
        $verOutput = & $cmd --version 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0 -and $verOutput -match 'Python\s+(\d+)\.(\d+)') {
            $major = [int]$Matches[1]; $minor = [int]$Matches[2]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 11)) {
                $pythonCmd = $cmd
                Write-OK "$cmd -> $($verOutput.Trim())"
                break
            } else {
                Write-Warn "$cmd -> $($verOutput.Trim()) (below 3.11, skipped)"
            }
        }
    } catch {}
}
if (-not $pythonCmd) {
    Write-Err "Python 3.11+ is not installed (or not on PATH)."
    Write-Host "   Install from https://www.python.org/downloads/ then restart PowerShell." -ForegroundColor Gray
    exit 1
}

# --- 2. Create venv ---
Write-Step "Step 2) Create .venv"
if (Test-Path '.venv') {
    Write-Warn ".venv already exists. Reusing. (Delete the folder to reinstall.)"
} else {
    & $pythonCmd -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Err 'venv creation failed'; exit 1 }
    Write-OK ".venv created"
}

$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Write-Err "Could not find .venv python.exe at: $VenvPython"
    exit 1
}

# --- 3. Upgrade pip + install requirements ---
Write-Step "Step 3) Upgrade pip + install requirements"
& $VenvPython -m pip install --upgrade pip --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Write-Err 'pip upgrade failed'; exit 1 }
Write-OK "pip upgraded"

# --no-cache-dir bypasses corrupted local pip cache (avoids
# "Cache entry deserialization failed" warnings)
# Visible progress so the user can see download status.
Write-Host "   (downloading ~30MB of packages - may take 2-5 minutes)" -ForegroundColor Gray
& $VenvPython -m pip install -r requirements.txt --no-cache-dir --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    Write-Err 'requirements install failed - see error output above'
    Write-Host "   Try: .\.venv\Scripts\python.exe -m pip cache purge" -ForegroundColor Gray
    exit 1
}
Write-OK "requirements.txt installed"

# --- 4. .env template ---
Write-Step "Step 4) .env file"
if (Test-Path '.env') {
    Write-OK ".env already exists"
} else {
    if (Test-Path '.env.example') {
        Copy-Item '.env.example' '.env'
        Write-OK ".env.example -> .env copied"
        Write-Warn "Open .env and fill in GEMINI_API_KEY before the next step."
    } else {
        Write-Err ".env.example is missing. Project files may be corrupted."
        exit 1
    }
}

# --- 5. Dry-run scan (no Gemini calls) ---
Write-Step "Step 5) Dry-run (scan only, no Gemini API calls)"
$env:PYTHONIOENCODING = 'utf-8'
& $VenvPython -m pipeline.main --title pepp-us --dry-run
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Dry-run failed - check CLOOP_CREATIVES_ROOT path in .env and the folder structure."
    exit 1
}

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "Setup complete. Next steps to run actual tagging:" -ForegroundColor Green
Write-Host ""
Write-Host "   .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "   python -m pipeline.main --title pepp-us --limit 3" -ForegroundColor White
Write-Host ""
Write-Host "   (--limit 3 first to validate, then remove --limit for full run)" -ForegroundColor Gray
Write-Host "=========================================================" -ForegroundColor Green
