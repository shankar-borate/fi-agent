@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM  ABC Bank FI Agent — Package for deployment
REM  Run this on your dev machine. Produces: fi-agent-deploy.zip
REM ─────────────────────────────────────────────────────────────────────────────
setlocal
cd /d "%~dp0"

echo.
echo  Packaging FI Agent...
echo.

REM ── Step 1: Build web frontend ───────────────────────────────────────────────
echo  [1/3] Building web frontend...
cd web
call npm run build
if errorlevel 1 ( echo  [ERROR] Web build failed & pause & exit /b 1 )
cd ..
echo  [OK]   web\dist\ ready

REM ── Step 2: Create temp staging folder ───────────────────────────────────────
echo  [2/3] Collecting files...
set "STAGE=%TEMP%\fi-agent-stage"
if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%\server"
mkdir "%STAGE%\web\dist"

REM Copy server Python code (exclude .venv, __pycache__, .env)
robocopy server "%STAGE%\server" /E /XD .venv __pycache__ .mypy_cache docs /XF .env *.pyc *.pyo *.zip patch_auditor.py >nul

REM Copy only web\dist (built output)
robocopy web\dist "%STAGE%\web\dist" /E >nul

REM ── Step 3: Zip using PowerShell ─────────────────────────────────────────────
echo  [3/3] Creating zip...
if exist fi-agent-deploy.zip del fi-agent-deploy.zip
powershell -NoProfile -Command "Compress-Archive -Path '%STAGE%\*' -DestinationPath '%~dp0fi-agent-deploy.zip' -CompressionLevel Optimal"
rmdir /s /q "%STAGE%"

echo.
echo  Done: fi-agent-deploy.zip
echo.
echo  Deploy commands (Linux):
echo    scp fi-agent-deploy.zip user@server:/opt/
echo    ssh user@server
echo    unzip fi-agent-deploy.zip -d /opt/fi-agent
echo    cd /opt/fi-agent/server
echo    chmod +x start.sh
echo    cp .env.example .env ^&^& nano .env
echo    ./start.sh setup
echo    ./start.sh
echo.
pause
