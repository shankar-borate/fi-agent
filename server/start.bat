@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM  ABC Bank FI Agent — Windows startup script
REM
REM  Usage:
REM    start.bat          Production mode
REM    start.bat dev      Development mode  (auto-reload on code change)
REM    start.bat setup    Setup only (venv + packages), don't start server
REM ─────────────────────────────────────────────────────────────────────────────
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "MODE=%~1"
set "VENV=.venv"
set "PYTHON=%VENV%\Scripts\python.exe"
set "PIP=%VENV%\Scripts\pip.exe"
set "PORT=8000"

echo.
echo  ================================================
echo   ABC Bank FI Agent - Server
echo  ================================================
echo.

REM ── 1. Python check ───────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found.
    echo          Download from https://python.org ^(3.11 or later^)
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  [INFO]  %%v

REM ── 2. Virtual environment ────────────────────────────────────────────────
if not exist "%VENV%\Scripts\python.exe" (
    echo  [SETUP] Creating virtual environment...
    python -m venv %VENV%
    if errorlevel 1 ( echo  [ERROR] venv creation failed & pause & exit /b 1 )
    echo  [SETUP] Virtual environment created.
) else (
    echo  [INFO]  Virtual environment found.
)

REM ── 3. Install / update packages ─────────────────────────────────────────
echo  [SETUP] Installing packages...
"%PIP%" install --upgrade pip --quiet
"%PIP%" install -r requirements.txt --quiet
if errorlevel 1 ( echo  [ERROR] pip install failed & pause & exit /b 1 )
echo  [SETUP] Packages ready.

REM ── 4. .env check ─────────────────────────────────────────────────────────
if not exist ".env" (
    echo.
    echo  [WARN]  .env file not found^^!
    echo          Create .env with these keys:
    echo            FI_AWS_ACCESS_KEY_ID=
    echo            FI_AWS_SECRET_ACCESS_KEY=
    echo            FI_AWS_REGION=ap-south-1
    echo            FI_OPENAI_API_KEY=
    echo            FI_GOOGLE_MAPS_API_KEY=
    echo            FI_STORAGE_ROOT=D:\fig
    echo.
) else (
    echo  [INFO]  .env found.
)

REM ── 5. Storage directory ──────────────────────────────────────────────────
for /f "tokens=2 delims==" %%s in ('findstr /i "FI_STORAGE_ROOT" .env 2^>nul') do set "STORAGE=%%s"
if "%STORAGE%"=="" set "STORAGE=D:\fig"
if not exist "%STORAGE%" (
    mkdir "%STORAGE%"
    echo  [SETUP] Storage folder created: %STORAGE%
) else (
    echo  [INFO]  Storage: %STORAGE%
)

REM ── 6. Build web frontend if dist missing ─────────────────────────────────
if not exist "..\web\dist\index.html" (
    echo  [SETUP] Web frontend not built — building now...
    where npm >nul 2>&1
    if errorlevel 1 (
        echo  [WARN]  npm not found. Run manually: cd ..\web ^&^& npm run build
    ) else (
        pushd ..\web
        call npm install --silent 2>nul
        call npm run build 2>nul
        if errorlevel 1 ( echo  [WARN]  Web build failed. UI at /fi/ will be unavailable. )
        else ( echo  [SETUP] Web frontend built. )
        popd
    )
) else (
    echo  [INFO]  Web frontend ready.
)

if /i "%MODE%"=="setup" (
    echo.
    echo  [DONE]  Setup complete. Run start.bat to launch server.
    pause & exit /b 0
)

REM ── 7. Start ──────────────────────────────────────────────────────────────
echo.
echo  ------------------------------------------------
echo   Starting server on port %PORT%
echo  ------------------------------------------------
echo   Customer App : http://localhost:%PORT%/fi/
echo   Auditor Portal: http://localhost:%PORT%/auditor/
echo   Dashboard    : http://localhost:%PORT%/
echo   API Docs     : http://localhost:%PORT%/docs
echo   Health Check : http://localhost:%PORT%/health
echo  ------------------------------------------------
echo   Press Ctrl+C to stop
echo.

if /i "%MODE%"=="dev" (
    echo  [MODE]  Development ^(auto-reload enabled^)
    echo.
    "%PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port %PORT% --reload
) else (
    echo  [MODE]  Production
    echo.
    "%PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port %PORT% --workers 1
)

endlocal
pause
