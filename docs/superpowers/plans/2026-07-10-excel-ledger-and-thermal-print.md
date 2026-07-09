# Beeba Boys 1001 End-to-End Billing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bills created from the dashboard, Telegram bot, or MCP tools auto-save to a local Excel ledger and auto-print on a 58mm ESC/POS thermal printer, with an analytics layer answering earnings + customer counts.

**Architecture:** Local JSON stays the source of truth; `ExcelStorage` mirrors it to `bills.xlsx`. A refactored `PrinterManager` renders each receipt once (escpos `Dummy`) and dispatches raw bytes to a configurable transport (windows/serial/usb/none). A shared `billing_service.create_and_print` is the single create+print path for web, API, bot, and an MCP server. Docs make it clone-and-run via opencode.

**Tech Stack:** Python 3.11+, Flask, openpyxl, Pillow, python-escpos, pywin32 (Windows only), `mcp` (MCP SDK), python-telegram-bot, pytest + pytest-mock.

## Global Constraints

- Runtime target: **Windows laptop**; code must also import/test on macOS/Linux (Windows-only deps behind markers/lazy imports).
- Storage backend used = **`ExcelStorage`** (local Excel + JSON). `SheetsManager` stays dormant, selected only if `credentials/service-account.json` exists. No Google Sheets setup in this build.
- **JSON (`data/bills.json`) is the source of truth.** Excel is a derived export; a locked/​open Excel file must never lose a bill or raise.
- Shop items in scope: **Jeans, Shirt, Tshirt, Accessories**. Shop name default: **Beeba Boys 1001**.
- Printer transports: `windows` (default), `serial`, `usb`, `none`. Any print failure → log + return `False`; **a bill always still saves** and requests never 500.
- 58mm printer = **384 dots / 32 chars** (Font A).
- Quick-bill defaults (bot/MCP when unspecified): customer `Walk-in`, payment `Cash`.
- `customers == bills` (each non-deleted bill today = one customer visit).
- TDD, DRY, YAGNI, frequent commits. Run tests with the venv: `./venv/bin/pytest`.

---

## File Structure

- `app/local_storage.py` — **modify**: add `get_today_bills()`.
- `app/excel_storage.py` — **create**: `ExcelStorage(LocalStorage)` + `_sync_excel()`.
- `app/storage.py` — **create**: cached `get_storage()` backend selector.
- `app/analytics.py` — **create**: `today_stats(storage)`.
- `app/receipt_logo.py` — **create**: `get_receipt_logo()` thermal bitmap.
- `app/printer.py` — **modify**: `render_bill_bytes` + `send` + transports + factories.
- `app/config.py` — **modify**: printer config keys.
- `app/billing_service.py` — **create**: `create_and_print(storage, printer, data)`.
- `app/routes/dashboard.py`, `app/routes/api.py` — **modify**: use `get_storage`, shared service, analytics, API auto-print.
- `app/telegram_bot.py` — **modify**: quick-bill + stats.
- `app/mcp_server.py` — **create**: MCP tools.
- `app/templates/index.html` — **modify**: Printer settings group (plus commit the already-made gold UI).
- `requirements.txt`, `.env.example`, `README.md`, `AGENTS.md` — **modify/create**.
- Tests: `tests/test_excel_storage.py`, `tests/test_analytics.py`, `tests/test_receipt_logo.py`, `tests/test_printer.py` (rewrite), `tests/test_bot.py` (extend), `tests/test_mcp.py` — **create/modify**.

---

### Task 0: Commit the existing gold/charcoal UI + add dependencies

**Files:**
- Modify: `requirements.txt`
- (working tree already has `app/templates/index.html` gold theme uncommitted)

**Interfaces:**
- Produces: installed deps (`openpyxl`, `Pillow`, `mcp`) for all later tasks.

- [ ] **Step 1: Add dependencies to `requirements.txt`**

Append these lines:

```
openpyxl>=3.1.0
Pillow>=10.0.0
mcp>=1.2.0
pywin32>=306; sys_platform == "win32"
```

- [ ] **Step 2: Install them into the venv**

Run: `./venv/bin/pip install openpyxl Pillow mcp`
Expected: `Successfully installed openpyxl-... Pillow-... mcp-...` (pywin32 is Windows-only; skip on macOS).

- [ ] **Step 3: Verify the suite is green before changes**

Run: `./venv/bin/pytest -q`
Expected: all existing tests pass.

- [ ] **Step 4: Commit the UI + deps**

```bash
git add app/templates/index.html requirements.txt
git commit -m "feat(ui): gold/charcoal luxury theme; add openpyxl/Pillow/mcp deps"
```

---

### Task 1: `LocalStorage.get_today_bills()`

**Files:**
- Modify: `app/local_storage.py`
- Test: `tests/test_local_storage.py`

**Interfaces:**
- Produces: `LocalStorage.get_today_bills() -> list[dict]` — today's **non-deleted** raw bill dicts (keys as stored in JSON: `bill_no`, `customer_name`, `total`, `payment_type`, `timestamp`, `status`, ...).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_local_storage.py`:

```python
    @backup_and_restore
    def test_get_today_bills_excludes_deleted(self):
        s = self._make_storage()
        b1 = s.add_bill("A", "", [{"name": "Shirt", "qty": 1, "price": 100}], 100, 100, "Cash")
        b2 = s.add_bill("B", "", [{"name": "Jeans", "qty": 1, "price": 200}], 200, 200, "UPI")
        s.delete_bill(b1)
        today = s.get_today_bills()
        assert len(today) == 1
        assert today[0]["customer_name"] == "B"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_local_storage.py::TestLocalStorage::test_get_today_bills_excludes_deleted -v`
Expected: FAIL — `AttributeError: 'LocalStorage' object has no attribute 'get_today_bills'`.

- [ ] **Step 3: Implement `get_today_bills`**

Add this method to `LocalStorage` in `app/local_storage.py` (after `get_today_earnings_by_payment`):

```python
    def get_today_bills(self) -> list[dict]:
        bills = _load_json(BILLS_PATH, [])
        today = datetime.now().strftime("%Y-%m-%d")
        return [
            b for b in bills
            if b.get("status") != "deleted" and b.get("timestamp", "").startswith(today)
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_local_storage.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add app/local_storage.py tests/test_local_storage.py
git commit -m "feat(storage): add LocalStorage.get_today_bills"
```

---

### Task 2: `ExcelStorage` backend

**Files:**
- Create: `app/excel_storage.py`
- Test: `tests/test_excel_storage.py`

**Interfaces:**
- Consumes: `LocalStorage`, `local_storage._load_json`, `local_storage.BILLS_PATH`.
- Produces: `ExcelStorage(xlsx_path: str = <data/bills.xlsx>)`, subclass of `LocalStorage`; overrides `add_bill/edit_bill/delete_bill/set_setting` to also write `bills.xlsx`; `_sync_excel()` regenerates the workbook; never raises on a locked file.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_excel_storage.py`:

```python
import os
import json
import pytest
from openpyxl import load_workbook
import app.local_storage as ls


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ls, "BILLS_PATH", str(tmp_path / "bills.json"))
    monkeypatch.setattr(ls, "SETTINGS_PATH", str(tmp_path / "settings.json"))
    from app.excel_storage import ExcelStorage
    return ExcelStorage(xlsx_path=str(tmp_path / "bills.xlsx"))


def test_add_bill_writes_json_and_xlsx(storage, tmp_path):
    storage.add_bill("Ramesh", "911", [{"name": "Shirt", "qty": 2, "price": 800}], 1600, 1600, "Cash")
    # JSON is the source of truth
    bills = json.load(open(str(tmp_path / "bills.json")))
    assert bills[-1]["customer_name"] == "Ramesh"
    # xlsx mirrors it
    wb = load_workbook(str(tmp_path / "bills.xlsx"))
    assert "Bills" in wb.sheetnames and "Summary" in wb.sheetnames
    rows = list(wb["Bills"].iter_rows(values_only=True))
    assert rows[0][2] == "Customer"          # header
    assert rows[1][2] == "Ramesh"            # data row


def test_summary_totals(storage, tmp_path):
    storage.add_bill("A", "", [{"name": "Shirt", "qty": 1, "price": 100}], 100, 100, "Cash")
    storage.add_bill("B", "", [{"name": "Jeans", "qty": 1, "price": 200}], 200, 200, "UPI")
    b3 = storage.add_bill("C", "", [{"name": "T", "qty": 1, "price": 50}], 50, 50, "Cash")
    storage.delete_bill(b3)  # excluded from summary
    wb = load_workbook(str(tmp_path / "bills.xlsx"))
    summary = list(wb["Summary"].iter_rows(values_only=True))
    assert summary[0] == ("Date", "Cash", "UPI", "Total", "Bill Count")
    # one day row: Cash=100, UPI=200, Total=300, Count=2
    assert summary[1][1] == 100 and summary[1][2] == 200
    assert summary[1][3] == 300 and summary[1][4] == 2


def test_lock_guard_never_loses_bill(storage, tmp_path, monkeypatch):
    from openpyxl import Workbook
    monkeypatch.setattr(Workbook, "save", lambda self, *a, **k: (_ for _ in ()).throw(PermissionError("open in Excel")))
    # Must not raise; JSON must still record the bill
    bill_no = storage.add_bill("Locked", "", [{"name": "Shirt", "qty": 1, "price": 500}], 500, 500, "Cash")
    assert bill_no >= 1
    bills = json.load(open(str(tmp_path / "bills.json")))
    assert bills[-1]["customer_name"] == "Locked"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/test_excel_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.excel_storage'`.

- [ ] **Step 3: Implement `ExcelStorage`**

Create `app/excel_storage.py`:

```python
"""
Billing Software — Excel ledger backend.
JSON stays the source of truth; bills.xlsx is a derived export rewritten on every change.
"""
import os
import logging

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from app import local_storage as ls
from app.local_storage import LocalStorage

logger = logging.getLogger("billing")

HEADER = ["Timestamp", "Bill No", "Customer", "Phone", "Items",
          "Total", "Paid", "Change", "Payment Type", "Status", "Deleted At"]


class ExcelStorage(LocalStorage):
    """LocalStorage + an Excel mirror at data/bills.xlsx."""

    def __init__(self, xlsx_path: str | None = None):
        self.xlsx_path = xlsx_path or os.path.join(ls.DATA_DIR, "bills.xlsx")

    # --- mutators: write JSON (super) then sync Excel ---
    def add_bill(self, *args, **kwargs):
        result = super().add_bill(*args, **kwargs)
        self._sync_excel()
        return result

    def edit_bill(self, *args, **kwargs):
        result = super().edit_bill(*args, **kwargs)
        self._sync_excel()
        return result

    def delete_bill(self, *args, **kwargs):
        result = super().delete_bill(*args, **kwargs)
        self._sync_excel()
        return result

    def set_setting(self, *args, **kwargs):
        result = super().set_setting(*args, **kwargs)
        self._sync_excel()
        return result

    def _sync_excel(self):
        try:
            bills = ls._load_json(ls.BILLS_PATH, [])
            wb = Workbook()
            ws = wb.active
            ws.title = "Bills"
            ws.append(HEADER)
            for cell in ws[1]:
                cell.font = Font(bold=True)
            ws.freeze_panes = "A2"

            del_fill = PatternFill("solid", fgColor="FFF0F0")
            for b in bills:
                ws.append([
                    b.get("timestamp", ""), b.get("bill_no", ""), b.get("customer_name", ""),
                    b.get("phone", ""), b.get("items", ""), b.get("total", 0), b.get("paid", 0),
                    b.get("change", 0), b.get("payment_type", ""), b.get("status", "active"),
                    b.get("deleted_at", ""),
                ])
                if b.get("status") == "deleted":
                    for cell in ws[ws.max_row]:
                        cell.fill = del_fill
            for row in ws.iter_rows(min_row=2, min_col=6, max_col=8):
                for cell in row:
                    cell.number_format = u"₹#,##0"

            summary = wb.create_sheet("Summary")
            summary.append(["Date", "Cash", "UPI", "Total", "Bill Count"])
            for cell in summary[1]:
                cell.font = Font(bold=True)
            days: dict[str, dict] = {}
            for b in bills:
                if b.get("status") == "deleted":
                    continue
                day = str(b.get("timestamp", ""))[:10]
                if not day:
                    continue
                agg = days.setdefault(day, {"Cash": 0.0, "UPI": 0.0, "total": 0.0, "count": 0})
                amount = float(b.get("total", 0) or 0)
                agg["total"] += amount
                agg["count"] += 1
                ptype = b.get("payment_type", "Cash")
                if ptype in ("Cash", "UPI"):
                    agg[ptype] += amount
            for day in sorted(days):
                a = days[day]
                summary.append([day, a["Cash"], a["UPI"], a["total"], a["count"]])

            tmp = self.xlsx_path + ".tmp"
            wb.save(tmp)
            os.replace(tmp, self.xlsx_path)
        except (PermissionError, OSError) as e:
            logger.warning(f"Excel sync skipped (file open/locked?): {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/test_excel_storage.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/excel_storage.py tests/test_excel_storage.py
git commit -m "feat(storage): ExcelStorage mirror with summary + lock guard"
```

---

### Task 3: `get_storage()` backend selector + wire routes

**Files:**
- Create: `app/storage.py`
- Modify: `app/routes/dashboard.py`, `app/routes/api.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Produces: `app.storage.get_storage() -> LocalStorage|ExcelStorage|SheetsManager` (cached). `ExcelStorage` when no `service-account.json`, else `SheetsManager`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_storage.py`:

```python
import app.storage as storage_mod
from app.excel_storage import ExcelStorage


def test_get_storage_returns_excel_without_credentials(monkeypatch):
    storage_mod._storage = None
    monkeypatch.setattr("app.config.Config.SERVICE_ACCOUNT_PATH", "/nope/service-account.json")
    s = storage_mod.get_storage()
    assert isinstance(s, ExcelStorage)


def test_get_storage_is_cached(monkeypatch):
    storage_mod._storage = None
    monkeypatch.setattr("app.config.Config.SERVICE_ACCOUNT_PATH", "/nope/service-account.json")
    assert storage_mod.get_storage() is storage_mod.get_storage()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.storage'`.

- [ ] **Step 3: Implement `get_storage`**

Create `app/storage.py`:

```python
"""Billing Software — storage backend selector (cached)."""
import os
from app.config import Config

_storage = None


def get_storage():
    global _storage
    if _storage is None:
        if os.path.exists(Config.SERVICE_ACCOUNT_PATH):
            from app.sheets import SheetsManager
            _storage = SheetsManager(Config.GOOGLE_SHEET_ID, Config.SERVICE_ACCOUNT_PATH)
        else:
            from app.excel_storage import ExcelStorage
            _storage = ExcelStorage()
    return _storage
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_storage.py -v`
Expected: PASS.

- [ ] **Step 5: Point the routes at `get_storage`**

In `app/routes/dashboard.py`, replace the whole `get_sheets()` function (lines ~16-26) with:

```python
from app.storage import get_storage

def get_sheets():
    return get_storage()
```

In `app/routes/api.py`, replace the whole `get_sheets()` function (lines ~13-22) and the module global `_sheets` with:

```python
from app.storage import get_storage

def get_sheets():
    return get_storage()
```

(Leave every existing `get_sheets()` call site unchanged — the alias keeps them working.)

- [ ] **Step 6: Run the full suite**

Run: `./venv/bin/pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add app/storage.py app/routes/dashboard.py app/routes/api.py tests/test_storage.py
git commit -m "feat(storage): central get_storage selector; ExcelStorage is default"
```

---

### Task 4: `today_stats` analytics + wire `/earnings`

**Files:**
- Create: `app/analytics.py`
- Modify: `app/routes/dashboard.py`, `app/routes/api.py`
- Test: `tests/test_analytics.py`

**Interfaces:**
- Consumes: any storage with `get_today_earnings()`, `get_today_earnings_by_payment()`, `get_today_bills()`.
- Produces: `app.analytics.today_stats(storage) -> {"date","total","cash","upi","bills","customers"}` where `customers == bills`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_analytics.py`:

```python
import pytest
import app.local_storage as ls
from app.analytics import today_stats


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ls, "BILLS_PATH", str(tmp_path / "bills.json"))
    monkeypatch.setattr(ls, "SETTINGS_PATH", str(tmp_path / "settings.json"))
    return ls.LocalStorage()


def test_today_stats(storage):
    storage.add_bill("A", "", [{"name": "Shirt", "qty": 1, "price": 1500}], 1500, 1500, "Cash")
    storage.add_bill("B", "", [{"name": "Jeans", "qty": 1, "price": 1000}], 1000, 1000, "UPI")
    b3 = storage.add_bill("C", "", [{"name": "T", "qty": 1, "price": 200}], 200, 200, "Cash")
    storage.delete_bill(b3)
    stats = today_stats(storage)
    assert stats["total"] == 2500
    assert stats["cash"] == 1500
    assert stats["upi"] == 1000
    assert stats["bills"] == 2
    assert stats["customers"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_analytics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.analytics'`.

- [ ] **Step 3: Implement `today_stats`**

Create `app/analytics.py`:

```python
"""Billing Software — analytics/reporting (shared by dashboard, bot, MCP)."""
from datetime import datetime


def today_stats(storage) -> dict:
    total = storage.get_today_earnings()
    by_pay = storage.get_today_earnings_by_payment()
    bills = len(storage.get_today_bills())
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total": total,
        "cash": by_pay.get("Cash", 0),
        "upi": by_pay.get("UPI", 0),
        "bills": bills,
        "customers": bills,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_analytics.py -v`
Expected: PASS.

- [ ] **Step 5: Add `bills`/`customers` to `/earnings` and `/api/earnings`**

In `app/routes/dashboard.py` `earnings()`, after computing `by_payment`, add before the `return`:

```python
        from app.analytics import today_stats
        stats = today_stats(sheets)
```

and add to the returned JSON dict: `"bills": stats["bills"], "customers": stats["customers"],`.

Apply the identical change to `get_earnings()` in `app/routes/api.py`.

- [ ] **Step 6: Run the full suite**

Run: `./venv/bin/pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add app/analytics.py app/routes/dashboard.py app/routes/api.py tests/test_analytics.py
git commit -m "feat(analytics): today_stats (earnings + customers/bills); expose on earnings endpoints"
```

---

### Task 5: `receipt_logo` thermal bitmap

**Files:**
- Create: `app/receipt_logo.py`
- Test: `tests/test_receipt_logo.py`

**Interfaces:**
- Produces: `app.receipt_logo.get_receipt_logo(width_dots: int = 384, path: str = <app/static/logo.png>) -> PIL.Image.Image | None`. Grayscale, auto-inverted if dark background, resized to `width_dots`, mode `"1"`. `None` if file missing or Pillow unavailable.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_receipt_logo.py`:

```python
import pytest
from PIL import Image
from app.receipt_logo import get_receipt_logo


def test_missing_file_returns_none(tmp_path):
    assert get_receipt_logo(384, str(tmp_path / "nope.png")) is None


def test_dark_logo_inverted_and_sized(tmp_path):
    # dark background (value 15) with a bright square
    img = Image.new("L", (100, 120), color=15)
    for x in range(40, 60):
        for y in range(50, 70):
            img.putpixel((x, y), 240)
    p = str(tmp_path / "logo.png")
    img.save(p)

    out = get_receipt_logo(384, p)
    assert out is not None
    assert out.mode == "1"
    assert out.size[0] == 384                 # resized to width
    assert out.getpixel((0, 0)) == 1          # dark bg -> inverted -> white paper
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/test_receipt_logo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.receipt_logo'`.

- [ ] **Step 3: Implement `get_receipt_logo`**

Create `app/receipt_logo.py`:

```python
"""Billing Software — prepare the shop logo as a 1-bit thermal-printable bitmap."""
import os

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "logo.png")
_cache: dict = {}


def get_receipt_logo(width_dots: int = 384, path: str = LOGO_PATH):
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    if not os.path.exists(path):
        return None

    mtime = os.path.getmtime(path)
    key = (path, width_dots)
    cached = _cache.get(key)
    if cached and cached["mtime"] == mtime:
        return cached["img"]

    img = Image.open(path).convert("L")

    # Auto-invert dark-background logos so paper (background) stays white.
    hist = img.histogram()
    pixels = sum(hist) or 1
    mean = sum(i * hist[i] for i in range(256)) / pixels
    if mean < 128:
        img = ImageOps.invert(img)

    w, h = img.size
    new_h = max(1, round(h * (width_dots / w)))
    img = img.resize((width_dots, new_h))
    img = img.convert("1")  # dither to 1-bit

    _cache[key] = {"mtime": mtime, "img": img}
    return img
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/test_receipt_logo.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/receipt_logo.py tests/test_receipt_logo.py
git commit -m "feat(printer): thermal logo bitmap with auto-invert"
```

---

### Task 6: Printer config keys

**Files:**
- Modify: `app/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces on `Config`: `PRINTER_TRANSPORT` (str, default `"windows"`), `PRINTER_SERIAL_PORT` (str), `PRINTER_BAUD` (int, 9600), `PRINTER_WINDOWS_NAME` (str), `PRINTER_WIDTH_DOTS` (int, 384), `PRINTER_CHARS` (int, 32).

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
def test_printer_config_defaults():
    from app.config import Config
    assert Config.PRINTER_TRANSPORT in ("windows", "serial", "usb", "none")
    assert Config.PRINTER_WIDTH_DOTS == 384
    assert Config.PRINTER_CHARS == 32
    assert isinstance(Config.PRINTER_BAUD, int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError: type object 'Config' has no attribute 'PRINTER_TRANSPORT'`.

- [ ] **Step 3: Add the keys**

In `app/config.py`, in the `# Printer` block (after `PRINTER_PRODUCT_ID`), add:

```python
    PRINTER_TRANSPORT = os.getenv("PRINTER_TRANSPORT", "windows")
    PRINTER_SERIAL_PORT = os.getenv("PRINTER_SERIAL_PORT", "")
    PRINTER_BAUD = int(os.getenv("PRINTER_BAUD", "9600"))
    PRINTER_WINDOWS_NAME = os.getenv("PRINTER_WINDOWS_NAME", "")
    PRINTER_WIDTH_DOTS = int(os.getenv("PRINTER_WIDTH_DOTS", "384"))
    PRINTER_CHARS = int(os.getenv("PRINTER_CHARS", "32"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat(config): printer transport/width config keys"
```

---

### Task 7: `PrinterManager` refactor — render once, dispatch to transports

**Files:**
- Modify: `app/printer.py`
- Modify: `app/routes/dashboard.py` (drop connect/disconnect usage), `app/main.py` (drop connect test)
- Test: `tests/test_printer.py` (rewrite)

**Interfaces:**
- Produces:
  - `PrinterManager(vendor_id=0x0416, product_id=0x5011, transport="usb", serial_port="", baud=9600, windows_name="", width_dots=384, chars=32, print_logo=True)`
  - `.render_bill_bytes(shop_name, shop_address, shop_contact, bill_no, customer_name, phone, items, total, paid, payment_type, footer="") -> bytes`
  - `.send(raw: bytes) -> bool`
  - `.print_bill(**same kwargs as render_bill_bytes) -> bool`
  - `PrinterManager.from_config() -> PrinterManager`
  - `PrinterManager.from_config_and_settings(storage) -> PrinterManager`

- [ ] **Step 1: Rewrite the printer tests**

Replace the entire contents of `tests/test_printer.py`:

```python
"""Tests for PrinterManager (mocked transports — no hardware)."""
import sys
import pytest
from app.printer import PrinterManager

BILL = dict(
    shop_name="Beeba Boys", shop_address="Main Road", shop_contact="9876543210",
    bill_no=5, customer_name="Ramesh", phone="9812345678",
    items=[{"name": "Shirt", "qty": 2, "price": 800}],
    total=1600, paid=1600, payment_type="Cash", footer="Thank you!",
)


def test_render_returns_bytes_with_shop_name():
    pm = PrinterManager(print_logo=False)
    raw = pm.render_bill_bytes(**BILL)
    assert isinstance(raw, (bytes, bytearray))
    assert len(raw) > 0
    assert b"Beeba Boys" in raw


def test_logo_makes_output_larger():
    with_logo = PrinterManager(print_logo=True).render_bill_bytes(**BILL)
    without = PrinterManager(print_logo=False).render_bill_bytes(**BILL)
    assert len(with_logo) > len(without)  # real logo at app/static/logo.png


def test_send_none_returns_false():
    assert PrinterManager(transport="none").send(b"x") is False


def test_send_usb_dispatch(mocker):
    dev = mocker.MagicMock()
    mocker.patch("escpos.printer.Usb", return_value=dev)
    assert PrinterManager(transport="usb").send(b"hello") is True
    dev._raw.assert_called_once_with(b"hello")


def test_send_serial_dispatch(mocker):
    dev = mocker.MagicMock()
    mocker.patch("escpos.printer.Serial", return_value=dev)
    pm = PrinterManager(transport="serial", serial_port="COM5")
    assert pm.send(b"hello") is True
    dev._raw.assert_called_once_with(b"hello")


def test_send_windows_dispatch(mocker):
    win = mocker.MagicMock()
    win.OpenPrinter.return_value = 42
    mocker.patch.dict(sys.modules, {"win32print": win})
    pm = PrinterManager(transport="windows", windows_name="POS58")
    assert pm.send(b"raw") is True
    win.OpenPrinter.assert_called_once_with("POS58")
    win.WritePrinter.assert_called_once_with(42, b"raw")


def test_send_swallows_exceptions(mocker):
    mocker.patch("escpos.printer.Usb", side_effect=Exception("no device"))
    assert PrinterManager(transport="usb").send(b"x") is False


def test_print_bill_calls_send(mocker):
    pm = PrinterManager(transport="none", print_logo=False)
    spy = mocker.spy(pm, "send")
    assert pm.print_bill(**BILL) is False
    spy.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/test_printer.py -v`
Expected: FAIL — `AttributeError` on `render_bill_bytes` / `send`.

- [ ] **Step 3: Rewrite `PrinterManager`**

Replace the entire contents of `app/printer.py`:

```python
"""Billing Software — thermal printer: render once (ESC/POS), dispatch to a transport."""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PrinterManager:
    """Renders a 58mm receipt to raw ESC/POS bytes and sends to a configurable transport."""

    def __init__(self, vendor_id: int = 0x0416, product_id: int = 0x5011,
                 transport: str = "usb", serial_port: str = "", baud: int = 9600,
                 windows_name: str = "", width_dots: int = 384, chars: int = 32,
                 print_logo: bool = True):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.transport = transport
        self.serial_port = serial_port
        self.baud = baud
        self.windows_name = windows_name
        self.width_dots = width_dots
        self.chars = chars
        self.print_logo = print_logo

    # ---- factories ----
    @classmethod
    def from_config(cls):
        from app.config import Config
        return cls(
            vendor_id=Config.PRINTER_VENDOR_ID, product_id=Config.PRINTER_PRODUCT_ID,
            transport=Config.PRINTER_TRANSPORT, serial_port=Config.PRINTER_SERIAL_PORT,
            baud=Config.PRINTER_BAUD, windows_name=Config.PRINTER_WINDOWS_NAME,
            width_dots=Config.PRINTER_WIDTH_DOTS, chars=Config.PRINTER_CHARS,
        )

    @classmethod
    def from_config_and_settings(cls, storage):
        pm = cls.from_config()
        try:
            t = storage.get_setting("printer_transport")
            if t:
                pm.transport = t
            for skey, attr in (("printer_windows_name", "windows_name"),
                               ("printer_serial_port", "serial_port")):
                v = storage.get_setting(skey)
                if v:
                    setattr(pm, attr, v)
        except Exception as e:
            logger.warning(f"Could not read printer settings: {e}")
        return pm

    # ---- render ----
    def render_bill_bytes(self, shop_name, shop_address, shop_contact, bill_no,
                          customer_name, phone, items, total, paid, payment_type,
                          footer="") -> bytes:
        from escpos.printer import Dummy
        d = Dummy()

        if self.print_logo:
            try:
                from app.receipt_logo import get_receipt_logo
                logo = get_receipt_logo(self.width_dots)
                if logo is not None:
                    d.set(align="center")
                    d.image(logo)
            except Exception as e:
                logger.warning(f"Logo skipped: {e}")

        change = round(paid - total, 2)
        d.set(align="center", bold=True, double_height=True, double_width=True)
        d.text(f"{shop_name}\n")
        d.set(align="center", bold=False, double_height=False, double_width=False)
        if shop_address:
            d.text(f"{shop_address}\n")
        if shop_contact:
            d.text(f"Tel: {shop_contact}\n")
        d.text("=" * self.chars + "\n")

        d.set(align="left")
        d.text(f"Bill No: {bill_no}\n")
        d.text(f"Date: {datetime.now().strftime('%d-%b-%Y %H:%M')}\n")
        d.text(f"Customer: {customer_name}\n")
        if phone:
            d.text(f"Phone: {phone}\n")
        d.text("-" * self.chars + "\n")

        d.set(bold=True)
        d.text(f"{'Item':<16}{'Qty':>4}{'Amt':>8}\n")
        d.set(bold=False)
        d.text("-" * self.chars + "\n")
        for item in items:
            name = str(item["name"])[:16]
            line_total = item["qty"] * item["price"]
            d.text(f"{name:<16}{item['qty']:>4}{line_total:>8.0f}\n")
        d.text("-" * self.chars + "\n")

        d.set(bold=True, double_height=True)
        d.set(align="right")
        d.text(f"Total: Rs {total:.0f}\n")
        d.set(bold=False, double_height=False)
        d.text(f"Paid: Rs {paid:.0f} ({payment_type})\n")
        if change >= 0:
            d.text(f"Change: Rs {change:.0f}\n")
        else:
            d.text(f"Due: Rs {abs(change):.0f}\n")

        d.set(align="center")
        d.text("=" * self.chars + "\n")
        if footer:
            d.text(f"{footer}\n")
        d.text("\n\n")
        d.cut()
        return d.output

    # ---- dispatch ----
    def send(self, raw: bytes) -> bool:
        t = (self.transport or "usb").lower()
        try:
            if t == "none":
                return False
            if t == "usb":
                from escpos.printer import Usb
                dev = Usb(self.vendor_id, self.product_id, timeout=5)
                dev._raw(raw)
                self._safe_close(dev)
                return True
            if t == "serial":
                from escpos.printer import Serial
                dev = Serial(self.serial_port, baudrate=self.baud, timeout=1)
                dev._raw(raw)
                self._safe_close(dev)
                return True
            if t == "windows":
                import win32print
                h = win32print.OpenPrinter(self.windows_name)
                try:
                    win32print.StartDocPrinter(h, 1, ("Bill", None, "RAW"))
                    win32print.StartPagePrinter(h)
                    win32print.WritePrinter(h, raw)
                    win32print.EndPagePrinter(h)
                    win32print.EndDocPrinter(h)
                finally:
                    win32print.ClosePrinter(h)
                return True
        except Exception as e:
            logger.warning(f"Print send failed ({t}): {e}")
            return False
        logger.warning(f"Unknown printer transport: {t}")
        return False

    @staticmethod
    def _safe_close(dev):
        try:
            dev.close()
        except Exception:
            pass

    def print_bill(self, **bill) -> bool:
        try:
            raw = self.render_bill_bytes(**bill)
        except Exception as e:
            logger.error(f"Receipt render failed: {e}")
            return False
        return self.send(raw)
```

- [ ] **Step 4: Update the callers that used the old connect() API**

In `app/routes/dashboard.py` `get_printer()`, replace the body with:

```python
def get_printer():
    from app.printer import PrinterManager
    return PrinterManager.from_config_and_settings(get_storage())
```

(This task's `generate_bill` still calls `printer.connect()` / `print_bill()` / `disconnect()`; those lines are replaced entirely in Task 8 when the shared service lands. To keep this task green, in `generate_bill` remove the `if printer.connect():` wrapper and the `printer.disconnect()` line, calling directly:)

```python
        printer = get_printer()
        printed = printer.print_bill(
            shop_name=Config.SHOP_NAME, shop_address=Config.SHOP_ADDRESS,
            shop_contact=Config.SHOP_CONTACT, bill_no=bill_no,
            customer_name=customer_name, phone=phone, items=items,
            total=total, paid=paid, payment_type=payment_type, footer=Config.BILL_FOOTER,
        )
```

In `app/main.py` `start_telegram()`, remove the three printer probe lines:

```python
    printer.connect()
    printer.disconnect()
```

and construct the printer with `PrinterManager.from_config()` instead of `PrinterManager(Config.PRINTER_VENDOR_ID, Config.PRINTER_PRODUCT_ID)`.

- [ ] **Step 5: Run the full suite**

Run: `./venv/bin/pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/printer.py app/routes/dashboard.py app/main.py tests/test_printer.py
git commit -m "feat(printer): render-once + transport dispatch (windows/serial/usb/none) with logo"
```

---

### Task 8: `billing_service.create_and_print` + wire dashboard & API

**Files:**
- Create: `app/billing_service.py`
- Modify: `app/routes/dashboard.py` (`generate_bill`), `app/routes/api.py` (`create_bill`)
- Test: `tests/test_billing_service.py`

**Interfaces:**
- Consumes: a storage (`add_bill`), a printer (`print_bill`) or `None`, `Config`.
- Produces: `app.billing_service.create_and_print(storage, printer, data: dict) -> dict`. `data` keys: `customer_name`, `phone`, `items` (list of `{name,qty,price}`), `payment_type`. Returns `{"success": True, "bill_no", "total", "printed"}` or `{"success": False, "error"}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_billing_service.py`:

```python
import pytest
import app.local_storage as ls
from app.billing_service import create_and_print


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ls, "BILLS_PATH", str(tmp_path / "bills.json"))
    monkeypatch.setattr(ls, "SETTINGS_PATH", str(tmp_path / "settings.json"))
    return ls.LocalStorage()


def test_creates_bill_and_reports_total(storage):
    res = create_and_print(storage, None, {
        "customer_name": "Ramesh", "phone": "911",
        "items": [{"name": "Shirt", "qty": 2, "price": 800}], "payment_type": "Cash",
    })
    assert res["success"] is True
    assert res["total"] == 1600
    assert res["bill_no"] >= 1
    assert res["printed"] is False  # printer=None


def test_requires_customer_and_items(storage):
    assert create_and_print(storage, None, {"items": []})["success"] is False
    assert create_and_print(storage, None, {"customer_name": "X", "items": []})["success"] is False


def test_calls_printer(storage, mocker):
    printer = mocker.MagicMock()
    printer.print_bill.return_value = True
    res = create_and_print(storage, printer, {
        "customer_name": "A", "items": [{"name": "Jeans", "qty": 1, "price": 1500}],
        "payment_type": "UPI",
    })
    assert res["printed"] is True
    printer.print_bill.assert_called_once()


def test_printer_exception_does_not_fail_bill(storage, mocker):
    printer = mocker.MagicMock()
    printer.print_bill.side_effect = Exception("offline")
    res = create_and_print(storage, printer, {
        "customer_name": "A", "items": [{"name": "Shirt", "qty": 1, "price": 100}],
    })
    assert res["success"] is True and res["printed"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/test_billing_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.billing_service'`.

- [ ] **Step 3: Implement `create_and_print`**

Create `app/billing_service.py`:

```python
"""Billing Software — single create+print path shared by web, API, bot, MCP."""
import logging
from app.config import Config

logger = logging.getLogger("billing")


def create_and_print(storage, printer, data: dict) -> dict:
    customer_name = (data.get("customer_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    items = data.get("items") or []
    payment_type = data.get("payment_type") or "Cash"

    if not customer_name:
        return {"success": False, "error": "customer_name is required"}
    if not items:
        return {"success": False, "error": "At least one item is required"}

    total = sum(i["qty"] * i["price"] for i in items)
    bill_no = storage.add_bill(customer_name, phone, items, total, total, payment_type)

    printed = False
    if printer is not None:
        try:
            printed = bool(printer.print_bill(
                shop_name=Config.SHOP_NAME, shop_address=Config.SHOP_ADDRESS,
                shop_contact=Config.SHOP_CONTACT, bill_no=bill_no,
                customer_name=customer_name, phone=phone, items=items,
                total=total, paid=total, payment_type=payment_type, footer=Config.BILL_FOOTER,
            ))
        except Exception as e:
            logger.warning(f"Print failed for bill #{bill_no}: {e}")
            printed = False

    return {"success": True, "bill_no": bill_no, "total": total, "printed": printed}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/test_billing_service.py -v`
Expected: PASS.

- [ ] **Step 5: Use the service in `generate_bill` (dashboard)**

In `app/routes/dashboard.py` `generate_bill`, after building the `items` list and validating it, replace the total/save/print block with:

```python
        from app.billing_service import create_and_print
        result = create_and_print(get_storage(), get_printer(), {
            "customer_name": customer_name, "phone": phone,
            "items": items, "payment_type": payment_type,
        })
        if not result["success"]:
            return jsonify(result), 400
        return jsonify({
            "success": True, "bill_no": result["bill_no"], "total": result["total"],
            "printed": result["printed"],
            "message": f"Bill #{result['bill_no']} generated successfully!",
        })
```

- [ ] **Step 6: Add auto-print to `/api/bill`**

In `app/routes/api.py` `create_bill`, replace the total/`add_bill`/return block with:

```python
        from app.billing_service import create_and_print
        from app.printer import PrinterManager
        result = create_and_print(get_sheets(), PrinterManager.from_config_and_settings(get_sheets()), {
            "customer_name": customer_name, "phone": phone,
            "items": items, "payment_type": payment_type,
        })
        if not result["success"]:
            return jsonify(result), 400
        return jsonify({
            "success": True, "bill_no": result["bill_no"], "total": result["total"],
            "printed": result["printed"], "shop": Config.SHOP_NAME,
        })
```

- [ ] **Step 7: Run the full suite**

Run: `./venv/bin/pytest -q`
Expected: all pass (including existing `tests/test_routes.py`).

- [ ] **Step 8: Commit**

```bash
git add app/billing_service.py app/routes/dashboard.py app/routes/api.py tests/test_billing_service.py
git commit -m "feat(billing): shared create_and_print; API auto-prints too"
```

---

### Task 9: Telegram quick-bill + stats

**Files:**
- Modify: `app/telegram_bot.py`
- Test: `tests/test_bot.py`

**Interfaces:**
- Produces on `BillBot`:
  - `_parse_quick_bill(text) -> dict | None` → `{"items", "customer_name", "payment_type"}` when the message contains items **and** a trigger word (`generate`, `print`, `bill`); else `None`. Defaults customer `Walk-in`, payment `Cash`; `name: X` sets customer; the word `upi`/`cash` sets payment.
  - `_stats_text(stats: dict) -> str` — one formatted reply for earnings + customers.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_bot.py`:

```python
    def test_quick_bill_defaults(self):
        bot = BillBot("test", None, None, [])
        qb = bot._parse_quick_bill("1 shirt=800, 1 jeans=1500, 1 accessories=200 generate this bill")
        assert qb is not None
        assert qb["customer_name"] == "Walk-in"
        assert qb["payment_type"] == "Cash"
        assert len(qb["items"]) == 3
        assert sum(i["qty"] * i["price"] for i in qb["items"]) == 2500

    def test_quick_bill_upi_and_name_override(self):
        bot = BillBot("test", None, None, [])
        qb = bot._parse_quick_bill("name: Ramesh 1 shirt=800 upi generate")
        assert qb["customer_name"] == "Ramesh"
        assert qb["payment_type"] == "UPI"
        assert len(qb["items"]) == 1

    def test_quick_bill_needs_trigger(self):
        bot = BillBot("test", None, None, [])
        # items but no trigger word -> not a quick bill
        assert bot._parse_quick_bill("1 shirt=800, 1 jeans=1500") is None

    def test_stats_text_has_numbers(self):
        bot = BillBot("test", None, None, [])
        txt = bot._stats_text({"date": "2026-07-10", "total": 2500, "cash": 1500,
                               "upi": 1000, "bills": 3, "customers": 3})
        assert "2500" in txt and "3" in txt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/test_bot.py -v`
Expected: FAIL — `AttributeError: 'BillBot' object has no attribute '_parse_quick_bill'`.

- [ ] **Step 3: Implement the helpers + wire into `handle_text`**

In `app/telegram_bot.py`, add these methods to `BillBot` (near `_parse_items`):

```python
    TRIGGER_WORDS = ("generate", "print", "make bill", "bill it")

    def _parse_quick_bill(self, text: str):
        """Return {items, customer_name, payment_type} if text is an immediate bill, else None."""
        import re
        low = text.lower()
        if not any(w in low for w in self.TRIGGER_WORDS):
            return None

        customer_name = "Walk-in"
        m = re.search(r"name\s*:\s*([A-Za-z][A-Za-z .]*)", text)
        if m:
            customer_name = m.group(1).strip()

        payment_type = "Cash"
        if re.search(r"\bupi\b", low):
            payment_type = "UPI"
        elif re.search(r"\bcash\b", low):
            payment_type = "Cash"

        # Strip override / trigger tokens before item parsing
        cleaned = text
        if m:
            cleaned = cleaned.replace(m.group(0), " ")
        cleaned = re.sub(r"(?i)\b(generate|print|this|bill it|make bill|the|bill|upi|cash)\b", " ", cleaned)

        items = self._parse_items(cleaned)
        if not items:
            return None
        return {"items": items, "customer_name": customer_name, "payment_type": payment_type}

    def _stats_text(self, stats: dict) -> str:
        return (
            f"📊 *{self.shop_name} — Today*\n\n"
            f"👥 Customers: *{stats.get('customers', 0)}*  (bills: {stats.get('bills', 0)})\n"
            f"💵 Cash: Rs {stats.get('cash', 0):.0f}\n"
            f"📱 UPI: Rs {stats.get('upi', 0):.0f}\n"
            f"──────────────\n"
            f"*Total: Rs {stats.get('total', 0):.0f}*"
        )

    async def _finalize_quick_bill(self, update, qb):
        from app.billing_service import create_and_print
        result = create_and_print(self.sheets, self.printer, qb)
        if not result.get("success"):
            await update.message.reply_text(f"❌ {result.get('error')}")
            return
        summary = ", ".join(f"{i['qty']}x {i['name']}={i['price']:.0f}" for i in qb["items"])
        msg = (
            f"✅ *Bill #{result['bill_no']} Generated!*\n\n"
            f"👤 {qb['customer_name']}\n📦 {summary}\n"
            f"💵 Total: Rs {result['total']:.0f}\n💳 {qb['payment_type']}\n"
        )
        msg += "🖨️ *Printed*" if result["printed"] else "⚠️ Print skipped (no printer)"
        await update.message.reply_text(msg, parse_mode="Markdown")
```

Then in `handle_text`, add — immediately after the `text = update.message.text.strip().lower()` line — a stats check, and a quick-bill check before the existing multi-step parsing:

```python
        if text in ("how many customers today", "how many customers", "how many bills",
                    "how many bills today", "stats", "summary", "/stats"):
            from app.analytics import today_stats
            await update.message.reply_text(self._stats_text(today_stats(self.sheets)),
                                            parse_mode="Markdown")
            return

        quick = self._parse_quick_bill(update.message.text)
        if quick:
            await self._finalize_quick_bill(update, quick)
            return
```

Also update `_show_earnings` to use the shared stats (replace its body):

```python
    async def _show_earnings(self, update: Update):
        try:
            from app.analytics import today_stats
            await update.message.reply_text(self._stats_text(today_stats(self.sheets)),
                                            parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/test_bot.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `./venv/bin/pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/telegram_bot.py tests/test_bot.py
git commit -m "feat(bot): quick-bill trigger + today stats replies"
```

---

### Task 10: MCP server

**Files:**
- Create: `app/mcp_server.py`
- Test: `tests/test_mcp.py`

**Interfaces:**
- Produces MCP tools (also importable as plain functions): `create_bill(customer_name, items, payment_type="Cash", phone="")`, `today_earnings()`, `recent_bills(limit=5)`, `search_bills(query)`. All operate on `app.storage.get_storage()`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mcp.py`:

```python
import pytest
import app.local_storage as ls
import app.mcp_server as mcp_server


@pytest.fixture(autouse=True)
def temp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ls, "BILLS_PATH", str(tmp_path / "bills.json"))
    monkeypatch.setattr(ls, "SETTINGS_PATH", str(tmp_path / "settings.json"))
    store = ls.LocalStorage()
    monkeypatch.setattr(mcp_server, "get_storage", lambda: store)
    monkeypatch.setenv("PRINTER_TRANSPORT", "none")
    return store


def test_create_bill_tool():
    res = mcp_server.create_bill("Ramesh", [{"name": "Shirt", "qty": 1, "price": 800}], "Cash")
    assert res["success"] is True
    assert res["total"] == 800


def test_today_earnings_tool():
    mcp_server.create_bill("A", [{"name": "Jeans", "qty": 1, "price": 1500}], "UPI")
    stats = mcp_server.today_earnings()
    assert stats["upi"] == 1500
    assert stats["customers"] == 1


def test_recent_and_search_tools():
    mcp_server.create_bill("Ramesh", [{"name": "Shirt", "qty": 1, "price": 800}], "Cash")
    assert len(mcp_server.recent_bills(5)) == 1
    assert len(mcp_server.search_bills("Ramesh")) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/pytest tests/test_mcp.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.mcp_server'`.

- [ ] **Step 3: Implement the MCP server**

Create `app/mcp_server.py`:

```python
"""Billing Software — MCP server exposing shop operations as agent tools (opencode/Claude)."""
from mcp.server.fastmcp import FastMCP

from app.storage import get_storage
from app.printer import PrinterManager
from app.analytics import today_stats
from app import billing_service

mcp = FastMCP("beeba-billing")


@mcp.tool()
def create_bill(customer_name: str, items: list, payment_type: str = "Cash", phone: str = "") -> dict:
    """Create a bill and auto-print it. items = [{"name","qty","price"}, ...]."""
    storage = get_storage()
    printer = PrinterManager.from_config_and_settings(storage)
    return billing_service.create_and_print(storage, printer, {
        "customer_name": customer_name, "phone": phone,
        "items": items, "payment_type": payment_type,
    })


@mcp.tool()
def today_earnings() -> dict:
    """Today's stats: total, cash, upi, bills, customers."""
    return today_stats(get_storage())


@mcp.tool()
def recent_bills(limit: int = 5) -> list:
    """Most recent bills (active first, then deleted)."""
    return get_storage().get_recent_bills(limit)


@mcp.tool()
def search_bills(query: str) -> list:
    """Search bills by customer name or phone."""
    return get_storage().search_bills(query)


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/test_mcp.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/mcp_server.py tests/test_mcp.py
git commit -m "feat(mcp): MCP server with create_bill/today_earnings/recent/search tools"
```

---

### Task 11: Settings modal — Printer group

**Files:**
- Modify: `app/templates/index.html`

**Interfaces:**
- Consumes: existing `/settings` (POST key/value) and `/settings/<key>` (GET) endpoints. Keys: `printer_transport`, `printer_windows_name`, `printer_serial_port`.

- [ ] **Step 1: Add the Printer fields to the settings modal**

In `app/templates/index.html`, inside `.modal-body` (after the Bill Footer `.form-group`, before the Shop Logo group), add:

```html
                <div class="form-group">
                    <label>Printer Connection</label>
                    <select id="settingsPrinterTransport">
                        <option value="windows">Windows printer (driver installed)</option>
                        <option value="serial">Bluetooth / Serial (COM port)</option>
                        <option value="usb">USB (ESC/POS)</option>
                        <option value="none">No printer</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Windows Printer Name</label>
                    <input type="text" id="settingsPrinterWinName" placeholder="e.g. POS58 Printer">
                </div>
                <div class="form-group">
                    <label>Bluetooth/Serial COM Port</label>
                    <input type="text" id="settingsPrinterCom" placeholder="e.g. COM5">
                </div>
```

- [ ] **Step 2: Load current printer settings on open**

In the `loadSettings()` JS function, extend the `Promise.all` to also fetch the printer keys and populate the fields:

```javascript
                const [addrRes, footerRes, ptRes, pwnRes, pcomRes] = await Promise.all([
                    fetch('/settings/shop_address'),
                    fetch('/settings/bill_footer'),
                    fetch('/settings/printer_transport'),
                    fetch('/settings/printer_windows_name'),
                    fetch('/settings/printer_serial_port'),
                ]);
                const addr = await addrRes.json();
                const footer = await footerRes.json();
                const pt = await ptRes.json();
                const pwn = await pwnRes.json();
                const pcom = await pcomRes.json();
                if (addr.success) document.getElementById('settingsAddress').value = addr.value || '';
                if (footer.success) document.getElementById('settingsFooter').value = footer.value || '';
                if (pt.success && pt.value) document.getElementById('settingsPrinterTransport').value = pt.value;
                if (pwn.success) document.getElementById('settingsPrinterWinName').value = pwn.value || '';
                if (pcom.success) document.getElementById('settingsPrinterCom').value = pcom.value || '';
```

- [ ] **Step 3: Save printer settings**

In the `settingsSave` click handler, after the existing `footer` save block, add three more saves:

```javascript
                saves.push(fetch('/settings', { method: 'POST',
                    body: new URLSearchParams({ key: 'printer_transport',
                        value: document.getElementById('settingsPrinterTransport').value }) }));
                saves.push(fetch('/settings', { method: 'POST',
                    body: new URLSearchParams({ key: 'printer_windows_name',
                        value: document.getElementById('settingsPrinterWinName').value.trim() }) }));
                saves.push(fetch('/settings', { method: 'POST',
                    body: new URLSearchParams({ key: 'printer_serial_port',
                        value: document.getElementById('settingsPrinterCom').value.trim() }) }));
```

- [ ] **Step 4: Manually verify in the browser**

Run: `FLASK_PORT=5055 PYTHONPATH=. ./venv/bin/python app/main.py web`
Open `http://localhost:5055`, click ⚙️, confirm the Printer group renders, pick a transport, Save → toast "Settings saved". Stop the server.

- [ ] **Step 5: Commit**

```bash
git add app/templates/index.html
git commit -m "feat(ui): printer transport settings in the settings modal"
```

---

### Task 12: Header — show customers today

**Files:**
- Modify: `app/templates/index.html`

- [ ] **Step 1: Add a customers stat to the header**

In `app/templates/index.html`, in `.header .stats`, change the sublabel line to include customers:

```html
                <div class="sublabel">
                    Cash: <span id="todayCash">₹0</span>
                    · UPI: <span id="todayUpi">₹0</span>
                    · 👥 <span id="todayCustomers">0</span>
                </div>
```

- [ ] **Step 2: Populate it in `loadEarnings()`**

In the `loadEarnings()` JS, after setting `todayUpi`, add:

```javascript
                document.getElementById('todayCustomers').textContent = data.customers ?? 0;
```

- [ ] **Step 3: Manually verify**

Run the server (as in Task 11 Step 4), create a bill from the dashboard, confirm the header shows `👥 1` and it increments per bill. Stop the server.

- [ ] **Step 4: Commit**

```bash
git add app/templates/index.html
git commit -m "feat(ui): show customers today in the header"
```

---

### Task 13: Docs — `.env.example`, README, AGENTS.md

**Files:**
- Modify: `.env.example`, `README.md`
- Create: `AGENTS.md`

- [ ] **Step 1: Update `.env.example`**

Replace the `# --- Printer ---` block in `.env.example` with:

```
# --- Printer (58mm ESC/POS, e.g. ATPOS H-58BT) ---
# transport: windows | serial | usb | none
PRINTER_TRANSPORT=windows
# windows: exact name of the installed printer (Control Panel > Devices & Printers)
PRINTER_WINDOWS_NAME=POS58 Printer
# serial (Bluetooth paired as a COM port): e.g. COM5
PRINTER_SERIAL_PORT=
PRINTER_BAUD=9600
# usb (needs WinUSB via Zadig on Windows)
PRINTER_VENDOR_ID=0x0416
PRINTER_PRODUCT_ID=0x5011
# 58mm = 384 dots / 32 chars
PRINTER_WIDTH_DOTS=384
PRINTER_CHARS=32
```

Also change the `# --- Google Sheets ---` comment block to note it is optional/legacy:

```
# --- Storage ---
# Default: local Excel ledger at data/bills.xlsx (no setup needed).
# OPTIONAL Google Sheets: drop credentials/service-account.json + set GOOGLE_SHEET_ID.
GOOGLE_SHEET_ID=
```

- [ ] **Step 2: Rewrite `README.md`**

Replace `README.md` with the full setup guide:

````markdown
# 🧾 Beeba Boys 1001 — MSME Billing Machine

Local-first billing for a retail shop. Dashboard + Telegram agent + 58mm thermal auto-print.
Saves every bill to a local **Excel** ledger. No cloud, no accounts. Open source (MIT).

## What it does

- **Dashboard** (browser on the shop LAN): pick item (Jeans / Shirt / Tshirt / Accessories),
  enter customer + phone, set price + qty, choose Cash/UPI → **Generate** → saves + prints.
- **Excel ledger**: every bill appended to `data/bills.xlsx` (Bills + per-day Summary).
- **Auto-print**: 58mm ESC/POS receipt with the shop logo (ATPOS H-58BT recommended).
- **Telegram agent**: type `1 shirt=800, 1 jeans=1500, 1 accessories=200 generate this bill`
  → creates + prints. Ask `how much today` or `how many customers today` → instant answer.
- **MCP tools**: connect **opencode** (or Claude) to operate the shop by tool call.

## Requirements

- Windows laptop (macOS/Linux work for everything except the Windows print transport)
- Python 3.11+
- A 58mm ESC/POS printer — **ATPOS H-58BT** (USB + Bluetooth) is the tested pick

## Setup with opencode (recommended)

Tell opencode:

> Clone `https://github.com/Kamal01CEO/beeba-boys-billing` and set it up following its README.

Or manually:

```bash
git clone https://github.com/Kamal01CEO/beeba-boys-billing
cd beeba-boys-billing
python -m venv venv
venv\Scripts\pip install -r requirements.txt   # Windows
# macOS/Linux: ./venv/bin/pip install -r requirements.txt
copy .env.example .env                          # then edit .env
```

Edit `.env`: set `SHOP_NAME`, the `PRINTER_*` values, `TELEGRAM_BOT_TOKEN`, `ALLOWED_USER_IDS`.

## Run

```bash
venv\Scripts\python app\main.py all    # web + telegram bot
# or: ... app\main.py web   (dashboard only)   |   ... app\main.py bot   (bot only)
```

Open `http://localhost:5000`.

## Printer setup (ATPOS H-58BT)

1. **Windows driver (recommended)** — install the H-58BT driver (USB or after Bluetooth pairing).
   In `.env`: `PRINTER_TRANSPORT=windows` and `PRINTER_WINDOWS_NAME=<exact printer name>`
   (Control Panel → Devices & Printers). Or set it in the dashboard ⚙️ Settings → Printer.
2. **Bluetooth as COM port** — pair the printer, note the outgoing COM port, then
   `PRINTER_TRANSPORT=serial`, `PRINTER_SERIAL_PORT=COM5`.
3. **USB (ESC/POS)** — `PRINTER_TRANSPORT=usb`; on Windows install WinUSB for the printer with
   [Zadig](https://zadig.akeo.ie/), then set `PRINTER_VENDOR_ID`/`PRINTER_PRODUCT_ID`.

If the printer is off/misconfigured, bills still save — printing just reports "skipped".

## Telegram setup

1. Telegram → **@BotFather** → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN`.
2. Message **@userinfobot** to get your numeric user id; put allowed ids (comma-separated) in
   `ALLOWED_USER_IDS` (empty = allow everyone — dev only).
3. Run `... app\main.py bot`. Commands: `/bill`, `/earnings`, `/recent`, `/search`, `/stats`,
   or natural language (`1 shirt=800 generate`, `how much today`, `how many customers today`).

## Connect opencode (MCP tools)

Run the MCP server: `venv\Scripts\python -m app.mcp_server`

Register it with opencode (in your opencode MCP config), e.g.:

```json
{
  "mcpServers": {
    "beeba-billing": {
      "command": "venv\\Scripts\\python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "C:/path/to/beeba-boys-billing"
    }
  }
}
```

Then ask opencode things like: *"make a bill: 1 shirt 800 for Ramesh cash"* or
*"what did we earn today"*. Tools: `create_bill`, `today_earnings`, `recent_bills`, `search_bills`.
See `AGENTS.md` for the full agent brief.

## Data & backup

- `data/bills.json` — source of truth (never lost).
- `data/bills.xlsx` — the ledger you open in Excel (Bills + Summary). Safe to have open; the app
  catches up on the next bill.
- Back up the `data/` folder.

## Development

```bash
./venv/bin/pytest -q      # run tests
```

## Tech

Python + Flask · openpyxl · python-escpos · Pillow · python-telegram-bot · MCP. MIT license.
````

- [ ] **Step 3: Create `AGENTS.md`**

Create `AGENTS.md`:

```markdown
# Beeba Boys 1001 Billing — Agent Guide (opencode / MCP)

You operate a retail shop's billing system. The shop is **Beeba Boys 1001**.
Items sold: **Jeans, Shirt, Tshirt, Accessories**. Currency: ₹ (INR). Payments: Cash or UPI.

## Tools (MCP server `beeba-billing`)

- `create_bill(customer_name, items, payment_type="Cash", phone="")` — creates + auto-prints a bill.
  `items` = list of `{"name","qty","price"}`. Returns `{success, bill_no, total, printed}`.
- `today_earnings()` — `{date, total, cash, upi, bills, customers}` (customers == bills today).
- `recent_bills(limit=5)` — latest bills.
- `search_bills(query)` — by customer name or phone.

## Workflows

- **Make a bill:** parse the user's line into items (name, qty, price). If no customer name is
  given, use `Walk-in`. If no payment given, use `Cash`. Call `create_bill`. Confirm the bill no,
  total, and whether it printed.
- **Report earnings / footfall:** call `today_earnings`; answer plainly
  ("Today: ₹2500 across 3 customers — ₹1500 cash, ₹1000 UPI").
- **Look up a customer:** call `search_bills`.

## Guardrails

- Never invent prices — ask if a price is missing.
- Confirm before creating a bill over ₹10,000 (likely a typo).
- Do not delete or edit bills unless explicitly asked.
- The printer failing does not fail the bill; report "saved, print skipped" if `printed` is false.
```

- [ ] **Step 4: Commit**

```bash
git add .env.example README.md AGENTS.md
git commit -m "docs: Windows/opencode setup, printer + telegram + MCP guide, AGENTS.md"
```

---

### Task 14: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `./venv/bin/pytest -q`
Expected: all pass, no warnings about collection errors.

- [ ] **Step 2: Smoke-test the web app end to end**

Run: `FLASK_PORT=5055 PYTHONPATH=. PRINTER_TRANSPORT=none ./venv/bin/python app/main.py web`
Then in another shell:

```bash
curl -s -X POST http://localhost:5055/generate-bill \
  -F customer_name=Ramesh -F phone=911 \
  -F 'item_name[]=Shirt' -F 'item_qty[]=2' -F 'item_price[]=800' \
  -F payment_type=Cash
curl -s http://localhost:5055/earnings
```

Expected: first returns `"success": true` with a `bill_no`; second returns `total`, `cash`,
`upi`, `bills`, `customers`. Confirm `data/bills.xlsx` now exists. Stop the server.

- [ ] **Step 3: Commit any final fixes, then stop**

If Step 1/2 surfaced fixes, commit them. Otherwise the branch is ready for review and (on the
user's approval) push.

---

## Self-Review

- **Spec coverage:** ExcelStorage (T2) + lock guard (T2) + summary (T2); JSON source of truth (T2);
  backend selector (T3); analytics `today_stats` + endpoints (T4) + header (T12) + bot stats (T9);
  receipt logo auto-invert (T5); printer config (T6); printer render/dispatch/transports (T7);
  shared create_and_print + API auto-print (T8); telegram quick-bill (T9); MCP server (T10);
  settings UI (T11); docs incl. opencode + AGENTS.md (T13); verification (T14). All spec sections mapped.
- **Placeholders:** none — every code/test step contains full code and exact commands.
- **Type consistency:** `today_stats` keys (`date,total,cash,upi,bills,customers`) used identically in
  T4/T9/T12; `create_and_print` return shape (`success,bill_no,total,printed`) consistent across
  T8/T9/T10; `PrinterManager` signature + `render_bill_bytes`/`send`/`print_bill`/factories consistent
  across T7/T8/T10.
- **Note:** Google Sheets stays dormant (spec non-goal); `SheetsManager` is only selected when a
  credential file exists and is not modified here.
```
