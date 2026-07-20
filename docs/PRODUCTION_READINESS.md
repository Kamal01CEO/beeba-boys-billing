# Beeba Boys Billing — Production Readiness

**Assessment date:** 2026-07-21
**Current decision:** Ready for controlled local testing; **not yet approved for live shop use** until the Windows laptop and physical printer checks below pass.

## What is ready

- Cash, UPI, and pay-later bills use one validated billing path.
- Customer debit accounts combine repeat itemized purchases and append-only repayments.
- Partial and full repayments are supported; overpayments are rejected.
- Debit sales do not incorrectly increase Cash/UPI collected totals. Repayments do.
- Percentage discounts retain the original subtotal and save the percentage, discount amount, and final payable total; collections and debit balances use the discounted total.
- Financial JSON writes are atomic and guarded across threads/processes.
- A damaged JSON file raises an error instead of being silently overwritten.
- Excel mirrors include Bills, Summary, Debit Accounts, and Debit Ledger sheets.
- Daily startup backups and a manual **Create Backup Now** control are available.
- Tests use isolated temporary data and cannot delete shop records.
- Waitress serves the Windows dashboard; the Flask development server is not the default.
- The default server binds to `127.0.0.1`, keeping the unauthenticated dashboard on the laptop only.
- Dashboard Cash/UPI reporting supports Today, Last 7 days, Last 30 days, and Last 1 year; debit repayments are counted when received and debit purchases are not counted as collections.
- Shop phone number is editable in Settings and is used on all newly printed bill and payment receipts.
- Per-user Windows automatic startup can run the Waitress server silently at login and creates a desktop dashboard shortcut.

## Must pass before shop launch

1. Install on the actual Windows laptop using `setup_windows.bat`.
2. Confirm the printer's exact Windows name and print at least 20 receipts, including a discounted Cash bill and a discounted debit bill showing Paid ₹0 and the correct Due value.
3. Restart Windows and verify the app opens, old bills remain, a new bill saves, and Excel refreshes.
4. Create a manual backup, copy it to a USB/cloud folder, and perform one restore drill on a separate test folder.
5. Confirm the laptop clock/timezone and Windows user account are correct.
6. Install automatic startup, sign out/in, verify the dashboard loads from the desktop shortcut, then perform a normal shutdown/startup persistence check.
7. Keep `FLASK_HOST=127.0.0.1`. If phones or other PCs must access the dashboard, authentication and HTTPS must be added before changing it to `0.0.0.0`.

## ATPOS H-58BT hardware status

- macOS detects the connected USB device as `USB Portable Printer` / STMicroelectronics with USB ID `0x0456:0x0808`.
- The USB ESC/POS runtime can discover, configure, open, and close the printer successfully. This model uses input endpoint `0x81` and output endpoint `0x03`; the project now carries those exact defaults.
- Bluetooth has created `/dev/cu.BlueToothPrinter`, but macOS currently reports the Bluetooth printer as not connected. Use USB as the primary connection.
- The first full-width `NOT A SALE` receipt was truncated physically even though USB returned success. Root cause evidence: 22.5 KB receipt with a 22 KB, 384×459-dot logo sent as one transfer, plus an unsupported cutter command.
- The H-58BT-safe profile now uses a 240-dot logo (full receipt about 9 KB), paced 512-byte writes with 25 ms gaps, a 500 ms final processing delay, and five-line manual-tear feed instead of cutting. The `TEST 2` retry returned `printed=True`; Kamal still needs to visually confirm it printed completely.
- Compact-layout follow-up after dashboard testing: receipts now use the H-58BT's Font B (42 characters/line), no double-size text, a 144-dot logo rendered with the more compatible `ESC *` column command, and three-line manual-tear feed. The full `TEST 3` payload is about 4 KB and returned `printed=True`; visual size/logo confirmation remains pending.
- The Windows printer queue name cannot be known until the ATPOS driver is installed on the shop laptop; copy it exactly from Windows Settings into the dashboard printer setting.

## Known limitations

- The debit ledger is designed for a single shop/laptop, not multi-user or multi-branch accounting.
- Google Sheets is a legacy backend and does not support the debit module. Use `STORAGE_BACKEND=excel`.
- Repayment reversal/correction is not yet exposed in the dashboard; mistakes require a controlled maintenance correction.
- Backup creation is local. Laptop loss is still data loss unless backups are copied off the laptop.
- There is no packaged Windows installer, automatic updater, or application login yet.
- GST/tax accounting, inventory/stock, returns/exchanges, expense accounting, and profit reporting are outside the current billing scope.

## Windows data locations

With the default settings, live data is stored under:

`%LOCALAPPDATA%\Beeba Boys 1001\data`

Important files:

- `bills.json` — source of truth for bills and itemized debit purchases
- `debit_payments.json` — append-only customer repayment entries
- `settings.json` — shop and printer settings
- `bills.xlsx` — human-readable Excel mirror
- `backups\` — timestamped ZIP backups

The exact active path is also shown inside Dashboard → Settings → Financial Data Location.
