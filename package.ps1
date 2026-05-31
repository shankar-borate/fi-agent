# ─────────────────────────────────────────────────────────────────────────────
#  ABC Bank FI Agent — Packager (run on dev machine, deploy zip to server)
#
#  What it does:
#    1. Builds web frontend  (web/src → web/dist)
#    2. Copies server Python code  (excludes .venv, __pycache__, .env)
#    3. Copies web/dist only  (not src or node_modules)
#    4. Zips everything → fi-agent-deploy.zip
#
#  Usage:   .\package.ps1
#  Output:  fi-agent-deploy.zip  (~1-2 MB)
# ─────────────────────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$out  = "$root\fi-agent-deploy.zip"

function Log([string]$step, [string]$msg, [string]$col = "Cyan") {
    Write-Host "  [$step] $msg" -ForegroundColor $col
}

Write-Host ""
Write-Host "  ABC Bank FI Agent — Packager" -ForegroundColor Blue
Write-Host ""

# ── Step 1: Build web frontend ───────────────────────────────────────────────
Log "1/3" "Building web frontend (npm run build)..." "Yellow"
Push-Location "$root\web"
npm run build
if ($LASTEXITCODE -ne 0) { Log "ERR" "Web build failed. Fix errors and retry." "Red"; exit 1 }
Pop-Location
Log "1/3" "Web frontend built → web/dist/" "Green"

# ── Step 2: Collect files into temp folder ───────────────────────────────────
Log "2/3" "Collecting files..." "Yellow"

$tmp = "$env:TEMP\fi-agent-pkg-$(Get-Random)"
New-Item -ItemType Directory -Path $tmp | Out-Null

# -- server/  (Python code only) --
$serverExclude = @(".venv", "__pycache__", ".mypy_cache", ".pytest_cache", "docs")
$fileExclude   = @("*.pyc", "*.pyo", ".env", "patch_auditor.py", "new_detail_func.txt", "*.zip")

New-Item -ItemType Directory "$tmp\server" | Out-Null

Get-ChildItem "$root\server" -Recurse | Where-Object {
    $rel = $_.FullName.Substring("$root\server\".Length)
    $skip = $false
    foreach ($d in $serverExclude) { if ($rel.StartsWith($d)) { $skip = $true; break } }
    foreach ($p in $fileExclude)   { if ($_.Name -like $p)    { $skip = $true; break } }
    -not $skip
} | ForEach-Object {
    $dest = $_.FullName.Replace("$root\server", "$tmp\server")
    if ($_.PSIsContainer) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
    else                  { Copy-Item $_.FullName -Destination $dest -Force }
}

# -- web/dist/  (built frontend only, no src/node_modules) --
Copy-Item "$root\web\dist" -Destination "$tmp\web\dist" -Recurse

# -- .env.example --
@"
# Rename this file to .env and fill in your values before starting the server.

FI_AWS_ACCESS_KEY_ID=
FI_AWS_SECRET_ACCESS_KEY=
FI_AWS_REGION=ap-south-1
FI_OPENAI_API_KEY=
FI_GOOGLE_MAPS_API_KEY=
FI_TRANSCRIBE_ENGINE=aws
FI_STORAGE_ROOT=/opt/fi-agent/data
"@ | Out-File "$tmp\server\.env.example" -Encoding utf8

# -- README --
@"
ABC Bank FI Agent — Deployment Package
=======================================

Contents
--------
  server/      Python backend (FastAPI + uvicorn)
  web/dist/    Built web frontend (served by the server at /fi/)

Quick Start (Linux)
-------------------
  cd server
  chmod +x start.sh
  cp .env.example .env && nano .env   # fill in API keys
  ./start.sh setup                    # first time: creates venv + installs packages
  ./start.sh                          # start server

  Then open:  http://<your-ip>:8000/fi/

All URLs
--------
  Customer App:    http://<ip>:8000/fi/
  Auditor Portal:  http://<ip>:8000/auditor/   (login: test / test)
  Dashboard:       http://<ip>:8000/
  API Docs:        http://<ip>:8000/docs
  Health:          http://<ip>:8000/health
"@ | Out-File "$tmp\README.txt" -Encoding utf8

# ── Step 3: Zip ───────────────────────────────────────────────────────────────
Log "3/3" "Creating zip..." "Yellow"
if (Test-Path $out) { Remove-Item $out -Force }
Compress-Archive -Path "$tmp\*" -DestinationPath $out -CompressionLevel Optimal
Remove-Item $tmp -Recurse -Force

$sizeMB = [math]::Round((Get-Item $out).Length / 1MB, 2)
Log "DONE" "fi-agent-deploy.zip created  ($sizeMB MB)" "Green"
Write-Host ""
Write-Host "  Deploy to Linux:" -ForegroundColor White
Write-Host "    scp fi-agent-deploy.zip user@server:/opt/" -ForegroundColor Yellow
Write-Host "    ssh user@server" -ForegroundColor Yellow
Write-Host "    cd /opt && unzip fi-agent-deploy.zip -d fi-agent" -ForegroundColor Yellow
Write-Host "    cd fi-agent/server && chmod +x start.sh" -ForegroundColor Yellow
Write-Host "    cp .env.example .env && nano .env" -ForegroundColor Yellow
Write-Host "    ./start.sh setup && ./start.sh" -ForegroundColor Yellow
Write-Host ""
