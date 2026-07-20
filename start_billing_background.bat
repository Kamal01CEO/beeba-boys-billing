@echo off
setlocal
cd /d "%~dp0"
set "BILLING_LOG_DIR=%LOCALAPPDATA%\Beeba Boys 1001\logs"
if not exist "%BILLING_LOG_DIR%" mkdir "%BILLING_LOG_DIR%"
call "%~dp0start_billing.bat" --background >> "%BILLING_LOG_DIR%\server.log" 2>&1
