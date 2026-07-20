@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo Run setup_windows.bat before installing automatic startup.
  pause
  exit /b 1
)

set "AUTOSTART_VBS=%~dp0start_billing_hidden.vbs"
for /f %%P in ('"venv\Scripts\python.exe" -c "from app.config import Config; print(Config.FLASK_PORT)"') do set "BILLING_PORT=%%P"
if not defined BILLING_PORT set "BILLING_PORT=5000"
set "DASHBOARD_URL=http://127.0.0.1:%BILLING_PORT%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$shell = New-Object -ComObject WScript.Shell;" ^
  "$startup = [Environment]::GetFolderPath('Startup');" ^
  "$shortcut = $shell.CreateShortcut((Join-Path $startup 'Beeba Boys Billing.lnk'));" ^
  "$shortcut.TargetPath = (Join-Path $env:SystemRoot 'System32\wscript.exe');" ^
  "$shortcut.Arguments = '""%AUTOSTART_VBS%""';" ^
  "$shortcut.WorkingDirectory = '%~dp0';" ^
  "$shortcut.Description = 'Start Beeba Boys Billing silently at Windows login';" ^
  "$shortcut.Save();" ^
  "$desktop = [Environment]::GetFolderPath('Desktop');" ^
  "Set-Content -Path (Join-Path $desktop 'Beeba Boys Billing.url') -Value '[InternetShortcut]`r`nURL=%DASHBOARD_URL%`r`n';"

if errorlevel 1 (
  echo Automatic startup installation failed.
  pause
  exit /b 1
)

echo.
echo Automatic startup installed for this Windows user.
echo The local server will start silently whenever this user signs in.
echo Use the Beeba Boys Billing desktop shortcut to open the dashboard.
echo.
pause
