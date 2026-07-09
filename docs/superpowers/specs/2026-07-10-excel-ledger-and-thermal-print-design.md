# Excel Ledger + 58mm Thermal Auto-Print — Design

**Date:** 2026-07-10
**Status:** Approved (pending spec review)

## Goal

Every bill created in the billing app must, automatically:

1. **Persist to a local Excel ledger** (`data/bills.xlsx`) — no cloud, no Google service account.
2. **Print on a 58mm ESC/POS thermal printer** (ATPOS H-58BT) with the Beeba Boys logo at the top.

Runtime target: **Windows PC**. Printer transport is user-selectable (Windows driver / Bluetooth COM / USB), defaulting to the installed Windows printer.

## Non-goals

- Google Sheets is not required. The existing `SheetsManager` stays in the codebase and is still selected automatically if a `service-account.json` is later added, but it is not part of this work.
- No battery/offline-queue system beyond the lock-guard described below.
- No change to the bill data model or the web UI look (the gold/charcoal theme stays).

## Storage: `ExcelStorage`

### Source of truth
Local JSON (`data/bills.json`) remains the **source of truth**. It is robust, already tested, and immune to file locks. Excel is a **derived export** rewritten from JSON on every mutation.

### New backend `app/excel_storage.py`
`ExcelStorage` **subclasses** the existing `LocalStorage` for minimal duplication:

- Inherits all read methods from `LocalStorage` (reads come from JSON — always safe).
- Overrides the four mutators — `add_bill`, `edit_bill`, `delete_bill`, `set_setting`: each calls `super()` (writes JSON) then `_sync_excel()`.
- `_sync_excel()` regenerates `data/bills.xlsx` from the full JSON via `openpyxl`.

### `bills.xlsx` layout
- **Bills** worksheet: header row (bold, frozen) = Timestamp, Bill No, Customer, Phone, Items, Total, Paid, Change, Payment Type, Status, Deleted At. One row per bill. `Total/Paid/Change` use a number format (`₹#,##0`). Rows with `status == "deleted"` are greyed (light red fill, strikethrough not required).
- **Summary** worksheet: per-day rows = Date, Cash, UPI, Total, Bill Count. Computed from non-deleted bills grouped by date.

### Excel-open lock guard
On Windows, `openpyxl` cannot save while the file is open in Excel.
- `_sync_excel()` wraps the save in `try/except (PermissionError, OSError)`.
- On failure: log a warning, leave JSON as the committed truth, do **not** raise. The bill still succeeds.
- Because the file is fully regenerated from JSON each time, the next successful write includes any rows that a locked write skipped → **no data loss**.
- Write to a temp file then `os.replace()` for atomicity where possible.

### Backend selection
`get_sheets()` in `app/routes/dashboard.py` and `app/routes/api.py` currently: `service-account.json` present → `SheetsManager`, else `LocalStorage`. Change the `else` branch to `ExcelStorage`. Extract this selection into one helper (`app/storage.py: get_storage()`) imported by both blueprints to remove the duplicated function.

### Dependency
Add `openpyxl` to `requirements.txt`.

## Printer: configurable transport + logo

### One format, many sinks
Build the receipt exactly once using `escpos.printer.Dummy()`, which yields the raw ESC/POS byte stream (text, image, cut). Dispatch those bytes to the configured transport. This guarantees identical output across USB / serial / Windows.

`app/printer.py` `PrinterManager` refactor:
- `render_bill_bytes(...) -> bytes` — builds header (logo bitmap + shop name + address/contact), bill meta, item table, totals, footer, cut — using `Dummy`.
- `send(raw: bytes) -> bool` — dispatches to the selected transport.
- `print_bill(...)` — `render_bill_bytes` then `send`. Same signature as today so callers are unchanged.

### Transports
Selected by `PRINTER_TRANSPORT` (config/settings): `windows` | `serial` | `usb` | `none`.

- **`windows`** (default, recommended): send raw bytes to an installed printer by name via `win32print` (`pywin32`) using a RAW datatype job. Config: `PRINTER_WINDOWS_NAME`.
- **`serial`**: `escpos.printer.Serial(port, baudrate)` — Bluetooth H-58BT paired as an outgoing COM port. Config: `PRINTER_SERIAL_PORT` (e.g. `COM5`), `PRINTER_BAUD` (default 9600). We only need its `_raw`/write to send prebuilt bytes.
- **`usb`**: existing `escpos.printer.Usb(vendor, product)`. Config: `PRINTER_VENDOR_ID`, `PRINTER_PRODUCT_ID`. (Windows requires WinUSB via Zadig — documented, not automated.)
- **`none`**: no-op, returns `False`. For dev / no hardware.

All transport failures are caught and logged; `print_bill` returns `False` (bill still saves). Never raises into the request.

### Config + Settings UI
- `.env` / `app/config.py`: `PRINTER_TRANSPORT` (default `windows`), plus the per-transport fields above and `PRINTER_WIDTH_DOTS` (default 384) / `PRINTER_CHARS` (default 32).
- Settings modal (`index.html`) gains a **Printer** group: a transport `<select>` and the single field that transport needs (printer name / COM port / USB IDs), persisted through the existing `/settings` endpoints. `PrinterManager` reads these settings at print time (settings override env), so USB↔Bluetooth is switchable with no code edits.

### Logo bitmap — `app/receipt_logo.py`
The logo is gold-on-near-black; printed as-is it becomes a black blob (thermal inks dark pixels). Transform for paper:
- Load `app/static/logo.png`, convert to grayscale.
- **Auto-invert if dark-background**: if mean luminance < ~50%, invert so the paper (background) stays white and the emblem prints black.
- Threshold/dither (Pillow `convert("1")`), resize to `PRINTER_WIDTH_DOTS` (384) preserving aspect.
- Cache the processed bitmap; regenerate when the logo file mtime changes.
- `render_bill_bytes` prints it centered via escpos `image()` above the shop name. If the logo file is missing or Pillow is unavailable, skip the bitmap and print the shop name only (no crash).

### Dependencies
Add `openpyxl`, ensure `Pillow` (already imported optionally) is in `requirements.txt`. `pywin32` is Windows-only for the `windows` transport — add to requirements with an environment marker (`pywin32; sys_platform == "win32"`) and document.

## Auto flow

- **Web dashboard** `POST /generate-bill`: already saves then prints. Unchanged flow; now saves to Excel and prints via configured transport with logo.
- **REST `POST /api/bill`**: add auto-print (user confirmed "both print"). Extract a shared `app/billing_service.py: create_and_print(storage, printer, data) -> result` used by both routes so print behaviour is identical and defined once.
- **Telegram bot**: already prints via its `PrinterManager`; it benefits from the refactor automatically. No behaviour change required.

## Error handling summary

| Failure | Behaviour |
|---|---|
| Excel file locked/open | Warn, JSON keeps the bill, next write catches up. No data loss. |
| Printer offline / bad config | Warn, `printed=False` in response, bill still saved. |
| Logo missing / Pillow absent | Print text-only header, no crash. |
| Any transport exception | Caught in `send()`, logged, returns `False`. Never 500s the request. |

## Testing

- **`tests/test_excel_storage.py`**: add_bill writes JSON + xlsx; reads come from JSON; Summary totals correct; deleted rows excluded from summary; lock guard (simulate `PermissionError` on save → bill still recorded in JSON, no raise).
- **`tests/test_printer.py`** (extend): `render_bill_bytes` returns non-empty bytes and includes an image command when logo present; transport dispatch calls the right sink (mock `win32print`, `Serial`, `Usb`); `none` transport returns `False`; all transport exceptions swallowed → `False`.
- **`tests/test_receipt_logo.py`**: dark logo is inverted (resulting bitmap background is white); output width == `PRINTER_WIDTH_DOTS`; missing file returns `None` gracefully.
- Existing route/bot/sheets tests stay green (backend swap is API-compatible).

## New / changed files

- `app/excel_storage.py` (new)
- `app/receipt_logo.py` (new)
- `app/billing_service.py` (new — shared create+print)
- `app/storage.py` (new — `get_storage()` selection helper)
- `app/printer.py` (refactor: Dummy render + transports)
- `app/config.py` (new printer config keys)
- `app/routes/dashboard.py`, `app/routes/api.py` (use shared storage helper + billing_service)
- `app/templates/index.html` (Printer settings group)
- `requirements.txt`, `.env.example`, `README.md`
- Tests as above.
