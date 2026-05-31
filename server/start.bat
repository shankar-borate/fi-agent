@echo off
:: server/start.bat — Create venv, install requirements, start FastAPI server
setlocal

cd /d "%~dp0"
echo === FI Agent Server ===

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Download from https://python.org
    pause & exit /b 1
)

for /f "tokens=*" %%v in ('python --version') do echo Python: %%v

:: Create virtual environment if missing
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 ( echo ERROR: venv creation failed & pause & exit /b 1 )
    echo Done.
) else (
    echo Virtual environment present - skipping creation
)

:: Install / update packages
echo.
echo Installing packages from requirements.txt...
.venv\Scripts\pip.exe install --upgrade pip --quiet
.venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 ( echo ERROR: pip install failed & pause & exit /b 1 )
echo Done.

:: Start server
echo.
echo Starting FastAPI server on http://0.0.0.0:8000 ...
echo API docs at http://localhost:8000/docs
echo Press Ctrl+C to stop
echo.
.venv\Scripts\python.exe main.py

endlocal
pause
