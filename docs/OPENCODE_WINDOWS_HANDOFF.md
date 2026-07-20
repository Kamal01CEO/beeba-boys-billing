# OpenCode Handoff — Beeba Boys Windows Laptop

Use this guide on the shop's Windows laptop after cloning the GitHub repository. Live finance data must remain outside the repository under `%LOCALAPPDATA%\Beeba Boys 1001\data`.

## Prompt to give OpenCode

> Set up this existing Beeba Boys billing repository on this Windows laptop. Read `README.md` and `docs/PRODUCTION_READINESS.md` completely first. Do not redesign the finance logic or delete/move existing data. Use `STORAGE_BACKEND=excel`, bind only to `127.0.0.1`, configure the installed ATPOS H-58BT Windows printer queue exactly, run the full test suite, perform one NOT A SALE printer test, install per-user automatic startup with `install_windows_autostart.bat`, and report the exact data, backup, log, and dashboard locations. Do not push or deploy anything without Kamal's approval.

## Installation order

1. Install Python 3.11 or newer from python.org and enable **Add Python to PATH**.
2. Install the ATPOS H-58BT Windows driver. Confirm the printer can print a Windows test page.
3. Clone the repository into a stable folder such as `C:\BeebaBoysBilling`—not Downloads or a temporary folder.
4. Double-click `setup_windows.bat`.
5. Open `.env` and verify:

   ```env
   STORAGE_BACKEND=excel
   FLASK_HOST=127.0.0.1
   FLASK_SERVER=waitress
   PRINTER_TRANSPORT=windows
   PRINTER_WINDOWS_NAME=THE EXACT NAME FROM WINDOWS SETTINGS
   ```

6. Double-click `start_billing.bat`. Open Settings and save the real shop name, address, phone number, footer, and exact Windows printer name.
7. Print a clearly marked NOT A SALE bill and a debit-payment receipt. Confirm the compact Font-B layout, small logo, complete printing, and manual-tear feed.
8. Double-click `install_windows_autostart.bat`. Sign out/in once and verify the server starts silently.
9. Open the desktop shortcut **Beeba Boys Billing**, or browse to the configured `http://127.0.0.1:<port>` URL.
10. Create a manual backup from Settings, copy it off the laptop, and perform the restore drill described in `docs/PRODUCTION_READINESS.md`.

## Daily operation and shutdown

- Each completed bill/payment is atomically saved immediately; the user does not need a separate Save or End Day button.
- Wait for the success/printed message before shutting down. Do not power off while a bill is still generating or printing.
- Normal Windows shutdown stops the local server. At the next user login, the Startup shortcut launches it silently again.
- The dashboard can then be opened from the desktop shortcut. If it does not load, inspect `%LOCALAPPDATA%\Beeba Boys 1001\logs\server.log`.

## Durable locations

- Data: `%LOCALAPPDATA%\Beeba Boys 1001\data`
- Backups: `%LOCALAPPDATA%\Beeba Boys 1001\data\backups`
- Background server log: `%LOCALAPPDATA%\Beeba Boys 1001\logs\server.log`
- Source code: the chosen clone folder, recommended `C:\BeebaBoysBilling`

Repository updates must never replace or delete the Local AppData folder.

## Verification commands for OpenCode

Run from the repository folder in Command Prompt:

```bat
venv\Scripts\python.exe -m pytest -q
venv\Scripts\python.exe -m py_compile app\config.py app\printer.py app\local_storage.py
```

Then verify `http://127.0.0.1:<port>/api/health` and test Today, Last 7 days, Last 30 days, and Last 1 year in the dashboard.
