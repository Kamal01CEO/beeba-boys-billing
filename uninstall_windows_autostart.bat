@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$startup = [Environment]::GetFolderPath('Startup');" ^
  "$shortcut = Join-Path $startup 'Beeba Boys Billing.lnk';" ^
  "if (Test-Path $shortcut) { Remove-Item $shortcut -Force }"
echo Automatic startup removed. Existing billing data was not touched.
pause
