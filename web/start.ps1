#!/usr/bin/env pwsh
# web/start.ps1 — Install npm packages and start the Vite dev server (Windows)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location $PSScriptRoot

Write-Host "=== FI Agent Web (Windows) ===" -ForegroundColor Cyan

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js not found. Download from https://nodejs.org"; exit 1
}
Write-Host "Node  : $(node --version)"
Write-Host "npm   : $(npm --version)"

if (-not (Test-Path "node_modules")) {
    Write-Host "`nInstalling npm packages..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) { Write-Error "npm install failed"; exit 1 }
    Write-Host "Done." -ForegroundColor Green
} else {
    Write-Host "node_modules present — skipping install"
}

Write-Host "`nStarting Vite dev server on http://localhost:5173 ..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop`n"
npm run dev
