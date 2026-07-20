# 🧾 Beeba Boys 1001 — MSME Billing Machine

Windows-first, local billing software for the Beeba Boys shop. It is currently ready for controlled laptop testing; complete the [production checklist](docs/PRODUCTION_READINESS.md) before live shop use.

## Features

- **Web Dashboard** — Generate bills from the shop laptop browser
- **Local Excel Ledger** — Bills, daily summary, debit accounts, and debit history
- **Customer Debits** — Repeat pay-later purchases, item history, partial/full repayments
- **Percentage Discounts** — Enter one percentage; subtotal, saving, final total, collection, and debit balance update automatically
- **Safe Local Storage** — Atomic source files, process locking, daily/manual ZIP backups
- **Telegram Bot** — Staff/owner can generate bills and check earnings from phone
- **Thermal Printer** — ESC/POS receipt printer support (USB)
- **Search** — Find bills by customer name or phone number
- **Daily Reports** — Auto-calculated earnings split by Cash/UPI
- **Flexible Reports** — Switch Cash/UPI collection totals between Today, 7 days, 30 days, and 1 year
- **Windows Auto-start** — Local server starts silently at login with a desktop dashboard shortcut

## Quick Start

On Windows:

1. Install Python 3.11 or newer from python.org and enable **Add Python to PATH**.
2. Double-click `setup_windows.bat` once.
3. Edit `.env` with the shop and printer details.
4. Double-click `start_billing.bat` whenever the shop opens.
5. After printer verification, double-click `install_windows_autostart.bat` once so the server starts silently at Windows login.

Windows/OpenCode handoff: [`docs/OPENCODE_WINDOWS_HANDOFF.md`](docs/OPENCODE_WINDOWS_HANDOFF.md)

For macOS/Linux development, run `./setup.sh` and then `python -m app.main web`.

## Screenshots

```
┌─────────────────┐  ┌─────────────────┐
│  🧾 New Bill    │  │  📋 Recent      │
│  Name: [____]   │  │  #5 Ram — Rs800  │
│  👖👔👕 Items   │  │  #4 Raj — Rs1500 │
│  Total: Rs 800  │  │  #3 Roy — Rs600  │
│  [💵Cash][📱UPI]│  │  Total:Rs 2900   │
│  [Generate Bill]│  └─────────────────┘
└─────────────────┘
```

## Architecture

```
┌───────────┐    ┌──────────┐    ┌───────────────┐
│ Web UI    │───▶│ Waitress │───▶│ JSON + Excel  │
│ (Browser) │    │ + Flask  │    │ (Local Data)  │
└───────────┘    └────┬─────┘    └───────────────┘
                      │
┌───────────┐    ┌────▼─────┐    ┌───────────────┐
│ Telegram  │───▶│ BillBot  │───▶│ Thermal       │
│ (Phone)   │    │ (Python) │    │ Printer (USB) │
└───────────┘    └──────────┘    └───────────────┘
```

## Usage

### Web Dashboard
- Open `http://127.0.0.1:5000` on the shop laptop
- Enter customer name → Select items → Optionally enter a discount percentage → Choose Cash, UPI, or Pay Later → Generate
- Bill auto-saves to the local ledger and prints (if printer connected)
- Open a customer under **Customer Debits** to add another purchase or receive a partial/full payment

### Telegram Bot
- Add your bot to Telegram and start a chat
- Commands:
  - `/bill 1 Shirt=800, 1 Jeans=1500` → Create a bill
  - `/earnings` → Today's total earnings
  - `/recent` → Last 5 bills
  - `/search Ramesh` → Find bills by name
- Natural language also works: "1 shirt=800, 1 jeans=1500"

### REST API (for agent integration)
```bash
# Create bill
curl -X POST http://localhost:5000/api/bill \
  -H "Content-Type: application/json" \
  -d '{"customer_name":"Ramesh","phone":"9876543210","items":[{"name":"Shirt","qty":1,"price":800}],"discount_percent":10,"payment_type":"Cash"}'

# Get earnings
curl http://localhost:5000/api/earnings
```

## Data and backups

On Windows, the dashboard stores its data outside the code folder at:

`%LOCALAPPDATA%\Beeba Boys 1001\data`

`bills.json` and `debit_payments.json` are the financial source files. `bills.xlsx` is the readable Excel mirror. The `backups` folder contains timestamped ZIP backups. Use **Settings → Create Backup Now**, then regularly copy the backup ZIP to a USB drive or cloud folder.

## Printer Setup

Supports 58mm/80mm ESC/POS thermal printers through a Windows driver, Bluetooth serial port, or direct USB.

- ATPOS H-58BT USB identity: `0x0456:0x0808` (`USB Portable Printer` / STMicroelectronics)
- ATPOS H-58BT endpoints: input `0x81`, output `0x03`
- The compact H-58BT profile uses its smaller 42-character Font B, a 144-dot centered header logo, paced 512-byte USB writes, and manual-tear feed because the supplied specifications do not list an automatic cutter.
- On macOS, prefer direct USB for testing. Bluetooth serial appears as `/dev/cu.BlueToothPrinter` when paired and connected.
- On Windows, install the printer driver and use Settings → Printer Connection → Windows printer.
- Enter the printer name exactly as it appears in Windows Settings.

## Development

```bash
# Run tests
./run_tests.sh

# Run specific test file
pytest tests/test_bot.py -v

# Start only the web UI
python -m app.main web

# Start only the Telegram bot
python -m app.main bot
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+, Flask |
| Storage | Atomic local JSON + Excel mirror |
| Windows server | Waitress |
| Bot | python-telegram-bot |
| Printer | python-escpos (USB) |
| PDF | ReportLab |
| Frontend | Vanilla HTML/CSS/JS |

## License

MIT — Free for commercial and personal use.
