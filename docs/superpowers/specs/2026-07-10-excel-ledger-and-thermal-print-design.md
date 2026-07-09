# Beeba Boys 1001 — End-to-End Billing System — Design

**Date:** 2026-07-10
**Status:** Approved (pending spec review)

## Goal

A self-contained, open-source billing system for the **Beeba Boys 1001** shop that runs
**locally on a Windows laptop**, and does the full loop:

1. **Dashboard**: pick item (Jeans / Shirt / Tshirt / Accessories) → enter customer name + phone →
   set amount per item → choose Cash or UPI → submit. Header shows today's earnings (Cash/UPI/Total)
   **and customers today (= bills)**.
2. **Save**: append the bill to a **local Excel ledger** (`data/bills.xlsx`). No cloud, no accounts.
3. **Auto-print**: print the receipt (with logo) on a **58mm ESC/POS thermal printer** (ATPOS H-58BT).
4. **Telegram agent**: from the phone, create a bill by typing
   `1 shirt=800, 1 jeans=1500, 1 accessories=200 generate this bill`, and ask
   `how much today` — bot answers earnings and auto-prints the bill.
5. **Agent tool access**: an **MCP server** exposes billing operations as tools so **opencode**
   (or any MCP client) can create bills and read data by tool call. REST API stays too.
6. **Open source**: push the repo with a complete README so anyone (via opencode) can clone,
   set up, and run it end-to-end, plus an opencode agent instruction file.

## Non-goals

- **Google Sheets is out of scope** for this build (chosen: local Excel only). The existing
  `SheetsManager` stays in the tree, dormant, as an optional/legacy backend; it is not wired,
  tested, or documented as the path here.
- No LLM inside the Telegram bot — it uses deterministic parsing (LLM operation is via opencode + MCP).
- No multi-shop / multi-user accounts, no auth beyond the Telegram allowlist.
- No battery/offline-queue beyond the Excel lock-guard below.

## Components

### 1. Storage — `ExcelStorage` (the only backend used)

**Source of truth** stays local JSON (`data/bills.json`) — robust, tested, immune to file locks.
Excel is a **derived export** rewritten from JSON on every mutation.

`app/excel_storage.py` **subclasses** `LocalStorage`:
- Inherits all read methods (reads come from JSON — always safe).
- Overrides the four mutators (`add_bill`, `edit_bill`, `delete_bill`, `set_setting`): each calls
  `super()` (writes JSON) then `_sync_excel()`.
- `_sync_excel()` regenerates `data/bills.xlsx` from full JSON via `openpyxl`.

`bills.xlsx`:
- **Bills** sheet: bold frozen header (Timestamp, Bill No, Customer, Phone, Items, Total, Paid,
  Change, Payment Type, Status, Deleted At); one row per bill; `₹#,##0` number format on money
  columns; deleted rows given a light-red fill.
- **Summary** sheet: per-day rows (Date, Cash, UPI, Total, Bill Count) from non-deleted bills.

**Excel-open lock guard:** `_sync_excel()` wraps the save in `try/except (PermissionError, OSError)`;
on failure it logs a warning, leaves JSON as truth, does **not** raise. Because the file is fully
regenerated from JSON each time, the next successful write catches up → **no data loss**. Write to a
temp file then `os.replace()` for atomicity.

**Backend selection** (`app/storage.py: get_storage()`, imported by both blueprints, the bot, and the
MCP server): returns `ExcelStorage`. (A single helper removes the duplicated `get_sheets()` in the two
route files.)

Dependency: add `openpyxl`.

### 2. Printer — configurable transport + logo

**One format, many sinks.** Build the receipt once with `escpos.printer.Dummy()` → raw ESC/POS bytes,
then dispatch to the configured transport. Identical output across USB / serial / Windows.

`app/printer.py` `PrinterManager` refactor:
- `render_bill_bytes(...) -> bytes` — logo bitmap + shop name + address/contact, bill meta, item table,
  totals, footer, cut.
- `send(raw: bytes) -> bool` — dispatch to transport.
- `print_bill(...)` keeps its current signature so callers are unchanged.

Transports via `PRINTER_TRANSPORT` = `windows` (default) | `serial` | `usb` | `none`:
- **`windows`** (default, recommended for the laptop): raw bytes to an installed printer by name via
  `win32print` (`pywin32`), RAW datatype job. Config: `PRINTER_WINDOWS_NAME`. Works for the H-58BT once
  its Windows driver is installed, whether connected by USB or Bluetooth.
- **`serial`**: `escpos.printer.Serial(port, baud)` — Bluetooth H-58BT paired as an outgoing COM port.
  Config: `PRINTER_SERIAL_PORT` (e.g. `COM5`), `PRINTER_BAUD` (default 9600).
- **`usb`**: existing `escpos.printer.Usb(vendor, product)`. Config: `PRINTER_VENDOR_ID`,
  `PRINTER_PRODUCT_ID`. (Windows needs WinUSB via Zadig — documented, not automated.)
- **`none`**: no-op, returns `False` (dev / no hardware).

All transport failures are caught, logged, return `False`; a bill never fails to save because of the
printer, and the request never 500s.

**Config + Settings UI:** `.env`/`app/config.py` gets `PRINTER_TRANSPORT`, the per-transport fields,
`PRINTER_WIDTH_DOTS` (384) and `PRINTER_CHARS` (32). The Settings modal gains a **Printer** group
(transport `<select>` + the one field that transport needs), saved via the existing `/settings`
endpoints; `PrinterManager` reads settings at print time (settings override env), so USB↔Bluetooth is
switchable with no code edits.

**Logo bitmap** — `app/receipt_logo.py`: the logo is gold-on-near-black; printed raw it becomes a black
blob. Transform: grayscale → **auto-invert if dark background** (mean luminance < ~50%) so paper stays
white and the emblem prints black → threshold/dither (`Pillow .convert("1")`) → resize to
`PRINTER_WIDTH_DOTS`. Cache, regenerate on logo mtime change. Print centered above the shop name.
If the logo is missing or Pillow is unavailable, print text-only (no crash).

Dependencies: `openpyxl`, `Pillow` (already used), `pywin32; sys_platform == "win32"`.

**Hardware:** ATPOS H-58BT (58mm, ESC/POS, USB + Bluetooth) integrates via any transport above and is a
confirmed fit; documented in the README as the recommended machine.

### 3. Telegram bot (built-in, deterministic)

`app/telegram_bot.py` — keep the existing command/NL bot, wired to `ExcelStorage` + `PrinterManager`,
and add a **quick-bill** path matching the requested one-liner.

- **Quick bill:** a message containing items **and** a trigger word (`generate`, `print`, `bill`) →
  create + auto-print **immediately**, no multi-step prompts. Defaults: customer = `Walk-in`,
  phone = empty, payment = `Cash`. Inline overrides recognised in the same message: a leading
  `name: Ramesh` sets the customer; the word `upi` (or `cash`) sets payment. The trigger phrase and any
  override tokens are stripped before item parsing.
  - Example: `1 shirt=800, 1 jeans=1500, 1 accessories=200 generate this bill` →
    bill for Walk-in, Cash, ₹2500, printed; bot replies with bill no + total + print status.
- **Items** recognised: Jeans, Shirt, Tshirt/T-Shirt, Accessories (parser already normalizes names).
- **Earnings / stats:** `how much today` / `today earnings` / `/earnings` → total + Cash + UPI.
  `how many customers today` / `how many bills` / `/stats` → replies with customers (= bills) today
  **and** the earnings summary (all from `today_stats`).
- **Recent / search:** `/recent`, `/search <name|phone>` (existing).
- The existing interactive flow (send items with no trigger → prompt name/phone/payment) stays for users
  who want it.
- **Auth:** `ALLOWED_USER_IDS` allowlist (existing). Empty = allow all (documented as dev-only).

### 4. MCP server — agent tool access

`app/mcp_server.py` — a stdio MCP server (Python `mcp` SDK) sharing the same `ExcelStorage`,
`PrinterManager`, and `billing_service`. Tools:
- `create_bill(customer_name, phone, items, payment_type)` → saves + auto-prints; returns
  `{bill_no, total, printed}`.
- `today_earnings()` → `today_stats` payload: `{date, total, cash, upi, bills, customers}`.
- `recent_bills(limit=5)` → list of recent bills.
- `search_bills(query)` → matches by name/phone.

Run as `python -m app.mcp_server` (stdio). Documented opencode/Claude config snippet points at it.
Dependency: add `mcp`.

### 4b. Analytics — `today_stats`

`app/analytics.py: today_stats(storage) -> dict` — one pure reporting function, reused by dashboard,
bot, and MCP so the numbers are computed once and always agree:

```
{ "date": "2026-07-10", "total": 2500, "cash": 1500, "upi": 1000,
  "bills": 3, "customers": 3 }
```

- `total` / `cash` / `upi` from existing `get_today_earnings()` + `get_today_earnings_by_payment()`.
- `bills` = count of today's **non-deleted** bills. **`customers` == `bills`** (each bill is one customer
  visit, per decision).
- Needs a new `get_today_bills()` on `LocalStorage` (inherited by `ExcelStorage`) returning today's
  non-deleted bills; `bills`/`customers` = `len(...)`. (Dormant `SheetsManager` is out of scope and not
  updated.)
- **Deferred (not in this build):** average bill value, top item. Structure leaves room to add them.

### 5. Shared billing service

`app/billing_service.py: create_and_print(storage, printer, data) -> result` — the single place that
validates items, computes total, saves, and auto-prints. Used by the web route, the REST API, the
Telegram bot, and the MCP server so behaviour is identical everywhere. REST `POST /api/bill` gains
auto-print (confirmed "both print").

### 6. Documentation (open source)

- **README.md** rewrite — end-to-end, Windows-first:
  - What it is; the Beeba Boys 1001 flow and screenshot.
  - Requirements: Python 3.11+, the ATPOS H-58BT printer, Windows.
  - **Clone via opencode**: exact prompt to hand opencode ("clone `<repo>` and set it up per README").
  - Setup: venv, `pip install -r requirements.txt`, copy `.env.example` → `.env`, fill shop name +
    printer transport/name + Telegram token + allowed user IDs.
  - Run: `python app/main.py web` / `bot` / `all`; open `http://localhost:5000`.
  - **Printer setup**: install the H-58BT Windows driver, set `PRINTER_TRANSPORT=windows` +
    `PRINTER_WINDOWS_NAME`; alternatives for Bluetooth COM (serial) and USB (Zadig).
  - **Telegram setup**: BotFather token, find your numeric user id, set the allowlist; command list.
  - **opencode setup**: how to register the MCP server, plus example operator prompts
    ("make a bill: 1 shirt 800 for Ramesh cash", "what did we earn today").
  - Data: where `bills.xlsx` / `bills.json` live, backup note.
- **AGENTS.md** — opencode agent instructions: the shop context, the tools available (MCP + REST),
  the standard workflows (create bill, read earnings, search), and guardrails.

## Data model (unchanged)

Bill: timestamp, bill_no (max+1), customer, phone, items (string `"1x Shirt=800"`), total, paid, change,
payment_type (Cash/UPI), status (active/deleted), deleted_at. Items in scope: Jeans, Shirt, Tshirt,
Accessories.

## Error handling summary

| Failure | Behaviour |
|---|---|
| Excel file open/locked | Warn, JSON keeps the bill, next write catches up. No data loss. |
| Printer offline / bad config | Warn, `printed=false`, bill still saved. |
| Logo missing / Pillow absent | Text-only header, no crash. |
| Transport exception | Caught in `send()`, logged, returns `False`. Never 500s. |
| Telegram unparteable message | Friendly help reply; no bill created. |

## Testing

- `tests/test_excel_storage.py`: add writes JSON + xlsx; reads from JSON; Summary totals; deleted rows
  excluded from summary; lock guard (simulate `PermissionError` → bill still in JSON, no raise).
- `tests/test_printer.py` (extend): `render_bill_bytes` non-empty and includes an image command when the
  logo is present; transport dispatch hits the right sink (mock `win32print`, `Serial`, `Usb`); `none`
  returns `False`; transport exceptions swallowed.
- `tests/test_receipt_logo.py`: dark logo inverted (white background result); width == `PRINTER_WIDTH_DOTS`;
  missing file returns `None`.
- `tests/test_bot.py` (extend): quick-bill trigger creates + prints with defaults; `upi` override;
  `name:` override; earnings reply; unauthorized blocked.
- `tests/test_analytics.py`: `today_stats` against a temp store with today/old/deleted bills →
  correct total/cash/upi and `bills == customers ==` today's non-deleted count.
- `tests/test_mcp.py`: each tool returns the expected shape against a temp `ExcelStorage`.
- Existing route/bot tests stay green (backend swap is API-compatible).

## New / changed files

- New: `app/excel_storage.py`, `app/receipt_logo.py`, `app/billing_service.py`, `app/storage.py`,
  `app/analytics.py`, `app/mcp_server.py`, `AGENTS.md`, tests listed above.
- Changed: `app/printer.py` (Dummy render + transports), `app/config.py` (printer keys),
  `app/routes/dashboard.py` + `app/routes/api.py` (shared helpers + API print; `/earnings` +
  `/api/earnings` return `bills`/`customers` from `today_stats`),
  `app/telegram_bot.py` (quick-bill), `app/templates/index.html` (Printer settings group; plus the
  already-made gold/charcoal UI, to be committed), `requirements.txt`, `.env.example`, `README.md`.

## Rollout

1. Build + test locally (Excel + bot verified; printer path unit-tested via mocks, hardware-verified by
   the user on the laptop).
2. Commit on `feat/excel-ledger-thermal-print`.
3. **Push / open-source is a separate, user-confirmed step** — the user (repo owner `Kamal01CEO`) approves
   the push to GitHub; the assistant does not push without that go-ahead.
