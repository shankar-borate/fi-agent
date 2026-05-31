@echo off
:: web/start.bat — Install npm packages and start Vite dev server
setlocal

cd /d "%~dp0"
echo === FI Agent Web ===

where node >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found. Download from https://nodejs.org
    pause & exit /b 1
)

for /f "tokens=*" %%v in ('node --version') do echo Node  : %%v
for /f "tokens=*" %%v in ('npm --version')  do echo npm   : %%v

if not exist "node_modules\" (
    echo.
    echo Installing npm packages...
    npm install
    if errorlevel 1 ( echo ERROR: npm install failed & pause & exit /b 1 )
    echo Done.
) else (
    echo node_modules present - skipping install
)

echo.
echo Starting Vite dev server on http://localhost:5173 ...
echo Press Ctrl+C to stop
echo.
npm run dev

endlocal
pause
