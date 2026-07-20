@echo off
setlocal
cd /d "%~dp0"
set "OPEN_BROWSER=1"
if /I "%~1"=="--background" set "OPEN_BROWSER=0"

if not exist "venv\Scripts\python.exe" (
  echo Billing software is not installed yet. Run setup_windows.bat first.
  pause
  exit /b 1
)

for /f %%P in ('"venv\Scripts\python.exe" -c "from app.config import Config; print(Config.FLASK_PORT)"') do set "BILLING_PORT=%%P"
if not defined BILLING_PORT set "BILLING_PORT=5000"

powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:%BILLING_PORT%/api/health ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 (
  if "%OPEN_BROWSER%"=="1" start "" "http://127.0.0.1:%BILLING_PORT%"
  exit /b 0
)

if "%OPEN_BROWSER%"=="1" start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:%BILLING_PORT%"
"venv\Scripts\python.exe" -m app.main web

if errorlevel 1 (
  echo.
  echo Billing stopped because of an error. Copy the message above and send it to the developer.
  pause
)
