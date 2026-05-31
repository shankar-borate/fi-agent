#!/usr/bin/env pwsh
# server/start.ps1 — Create venv, install requirements, start FastAPI server (Windows)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location $PSScriptRoot

Write-Host "=== FI Agent Server (Windows) ===" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found. Download from https://python.org"; exit 1
}
Write-Host "Python: $(python --version)"

# ── Virtual environment ──────────────────────────────────────────────────
$venv = ".venv"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    Write-Host "`nCreating virtual environment..." -ForegroundColor Yellow
    python -m venv $venv
    Write-Host "Done." -ForegroundColor Green
} else {
    Write-Host "Virtual environment present — skipping creation"
}

$pip    = "$venv\Scripts\pip.exe"
$python = "$venv\Scripts\python.exe"

# ── Install packages ────────────────────────────────────────────────────
Write-Host "`nInstalling/updating packages from requirements.txt..." -ForegroundColor Yellow
& $pip install --upgrade pip --quiet
& $pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed"; exit 1 }
Write-Host "Done." -ForegroundColor Green

# ── Start server ────────────────────────────────────────────────────────
Write-Host "`nStarting FastAPI server on http://0.0.0.0:8000 ..." -ForegroundColor Cyan
Write-Host "Docs at http://localhost:8000/docs"
Write-Host "Press Ctrl+C to stop`n"
& $python main.py
