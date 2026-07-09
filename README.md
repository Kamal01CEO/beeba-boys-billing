# 🧾 Beeba Boys 1001 — MSME Billing Machine

Production-ready billing software for MSME retail shops. No GST. Local-first. Open source.

## Features

- **Web Dashboard** — Generate bills from any browser on the local network
- **Google Sheets** — All transactions auto-saved to cloud (no database to manage)
- **Telegram Bot** — Staff/owner can generate bills and check earnings from phone
- **Thermal Printer** — ESC/POS receipt printer support (USB)
- **PDF Backup** — Bill generation to PDF when no printer is available
- **Search** — Find bills by customer name or phone number
- **Daily Reports** — Auto-calculated earnings split by Cash/UPI

## Quick Start

```bash
# 1. Setup
git clone https://github.com/Kamal01CEO/beeba-boys-billing.git
cd beeba-boys-billing
./setup.sh

# 2. Configure
cp .env.example .env
# Edit .env with your Google Sheet ID and Telegram bot token

# 3. Place service account
# Download from Google Cloud Console → put in credentials/service-account.json

# 4. Run
python app/main.py
# Open http://localhost:5000
```

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
│ Web UI    │───▶│ Flask    │───▶│ Google Sheets │
│ (Browser) │    │ (Python) │    │ (Cloud DB)    │
└───────────┘    └────┬─────┘    └───────────────┘
                      │
┌───────────┐    ┌────▼─────┐    ┌───────────────┐
│ Telegram  │───▶│ BillBot  │───▶│ Thermal       │
│ (Phone)   │    │ (Python) │    │ Printer (USB) │
└───────────┘    └──────────┘    └───────────────┘
```

## Usage

### Web Dashboard
- Open `http://localhost:5000` on any device in your network
- Enter customer name → Select items → Choose payment → Generate
- Bill auto-saves to Google Sheets and prints (if printer connected)

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
  -d '{"customer_name":"Ramesh","phone":"9876543210","items":[{"name":"Shirt","qty":1,"price":800}],"payment_type":"Cash"}'

# Get earnings
curl http://localhost:5000/api/earnings
```

## Google Sheets Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable Google Sheets API & Google Drive API
3. Create a Service Account → Download JSON key
4. Rename the key to `service-account.json` and place in `credentials/`
5. Create a Google Sheet → Share it with the service account email (Editor)
6. Copy the Sheet ID from the URL → Paste into `.env` as `GOOGLE_SHEET_ID`

The software auto-creates the required worksheets (Bills, Settings).

## Printer Setup

Supports 58mm/80mm ESC/POS thermal printers via USB.

- Default vendor/product IDs: `0x0416:0x5011`
- Find your printer: `lsusb | grep -i printer`
- Update `PRINTER_VENDOR_ID` and `PRINTER_PRODUCT_ID` in `.env`

## Development

```bash
# Run tests
./run_tests.sh

# Run specific test file
pytest tests/test_bot.py -v

# Start only the web UI
python app/main.py web

# Start only the Telegram bot
python app/main.py bot
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.9+, Flask |
| Database | Google Sheets (via gspread) |
| Bot | python-telegram-bot |
| Printer | python-escpos (USB) |
| PDF | ReportLab |
| Frontend | Vanilla HTML/CSS/JS |

## License

MIT — Free for commercial and personal use.
