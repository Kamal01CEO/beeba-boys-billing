@echo off
setlocal
cd /d "%~dp0"

echo Setting up Beeba Boys Billing...
where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher was not found. Install Python 3.11 or newer from python.org first.
  pause
  exit /b 1
)

if not exist "venv\Scripts\python.exe" (
  py -3 -m venv venv
  if errorlevel 1 goto :failed
)

"venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo Setup complete.
echo 1. Open .env and set SHOP_NAME and printer settings.
echo 2. Double-click start_billing.bat and complete one real printer test.
echo 3. Double-click install_windows_autostart.bat to start billing automatically at login.
pause
exit /b 0

:failed
echo.
echo Setup failed. Copy the error above and send it to the developer.
pause
exit /b 1
