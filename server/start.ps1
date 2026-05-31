#!/usr/bin/env pwsh
# ─────────────────────────────────────────────────────────────────────────────
#  ABC Bank FI Agent — PowerShell startup script (Windows)
#
#  Usage:
#    .\start.ps1           Production mode
#    .\start.ps1 dev       Development mode (auto-reload)
#    .\start.ps1 setup     Setup only, don't start server
# ─────────────────────────────────────────────────────────────────────────────
param([string]$Mode = "")

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$PORT   = 8000
$VENV   = ".venv"
$PYTHON = "$VENV\Scripts\python.exe"
$PIP    = "$VENV\Scripts\pip.exe"

function Write-Step([string]$tag, [string]$msg, [string]$color = "Cyan") {
    Write-Host "  [$tag] $msg" -ForegroundColor $color
}

Write-Host ""
Write-Host "  ================================================" -ForegroundColor Blue
Write-Host "   ABC Bank FI Agent - Server" -ForegroundColor Blue
Write-Host "  ================================================" -ForegroundColor Blue
Write-Host ""

# ── 1. Python check ────────────────────────────────────────────────────────
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Step "ERROR" "Python not found. Download from https://python.org (3.11+)" "Red"
    exit 1
}
Write-Step "INFO" "$(python --version)"

# ── 2. Virtual environment ─────────────────────────────────────────────────
if (-not (Test-Path "$VENV\Scripts\python.exe")) {
    Write-Step "SETUP" "Creating virtual environment..." "Yellow"
    python -m venv $VENV
    Write-Step "SETUP" "Virtual environment created." "Green"
} else {
    Write-Step "INFO" "Virtual environment found."
}

# ── 3. Install packages ────────────────────────────────────────────────────
Write-Step "SETUP" "Installing packages..." "Yellow"
& $PIP install --upgrade pip --quiet
& $PIP install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) { Write-Step "ERROR" "pip install failed" "Red"; exit 1 }
Write-Step "SETUP" "Packages ready." "Green"

# ── 4. .env check ─────────────────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    Write-Host ""
    Write-Step "WARN" ".env file not found!" "Yellow"
    Write-Host "         Create .env with:" -ForegroundColor Yellow
    @(
        "  FI_AWS_ACCESS_KEY_ID=",
        "  FI_AWS_SECRET_ACCESS_KEY=",
        "  FI_AWS_REGION=ap-south-1",
        "  FI_OPENAI_API_KEY=",
        "  FI_GOOGLE_MAPS_API_KEY=",
        "  FI_STORAGE_ROOT=D:\fig"
    ) | ForEach-Object { Write-Host "          $_" -ForegroundColor DarkYellow }
    Write-Host ""
} else {
    Write-Step "INFO" ".env found."
}

# ── 5. Storage directory ───────────────────────────────────────────────────
$storage = "D:\fig"
if (Test-Path ".env") {
    $line = Select-String -Path ".env" -Pattern "^FI_STORAGE_ROOT\s*=" |
            Select-Object -First 1
    if ($line) { $storage = ($line.Line -split "=", 2)[1].Trim() }
}
if (-not (Test-Path $storage)) {
    New-Item -ItemType Directory -Path $storage -Force | Out-Null
    Write-Step "SETUP" "Storage folder created: $storage" "Green"
} else {
    Write-Step "INFO" "Storage: $storage"
}

# ── 6. Web frontend ────────────────────────────────────────────────────────
$webDist = "..\web\dist\index.html"
if (-not (Test-Path $webDist)) {
    Write-Step "SETUP" "Web frontend not built — building now..." "Yellow"
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Push-Location "..\web"
        npm install --silent 2>$null
        npm run build 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Step "WARN" "Web build failed. /fi/ UI will be unavailable." "Yellow"
        } else {
            Write-Step "SETUP" "Web frontend built." "Green"
        }
        Pop-Location
    } else {
        Write-Step "WARN" "npm not found. Run manually: cd ..\web; npm run build" "Yellow"
    }
} else {
    Write-Step "INFO" "Web frontend ready."
}

if ($Mode -eq "setup") {
    Write-Host ""
    Write-Step "DONE" "Setup complete. Run .\start.ps1 to launch server." "Green"
    exit 0
}

# ── 7. Start ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ------------------------------------------------" -ForegroundColor Blue
Write-Host "   Starting server on port $PORT" -ForegroundColor Blue
Write-Host "  ------------------------------------------------" -ForegroundColor Blue
Write-Host "   Customer App:  http://localhost:$PORT/fi/" -ForegroundColor White
Write-Host "   Auditor Portal: http://localhost:$PORT/auditor/" -ForegroundColor White
Write-Host "   Dashboard:     http://localhost:$PORT/" -ForegroundColor White
Write-Host "   API Docs:      http://localhost:$PORT/docs" -ForegroundColor White
Write-Host "   Health Check:  http://localhost:$PORT/health" -ForegroundColor White
Write-Host "  ------------------------------------------------" -ForegroundColor Blue
Write-Host "   Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

if ($Mode -eq "dev") {
    Write-Step "MODE" "Development (auto-reload enabled)" "Yellow"
    Write-Host ""
    & $PYTHON -m uvicorn main:app --host 0.0.0.0 --port $PORT --reload
} else {
    Write-Step "MODE" "Production" "Cyan"
    Write-Host ""
    & $PYTHON -m uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1
}
