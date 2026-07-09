"""
Billing Software — Google Sheets Integration
"""
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import Optional

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsManager:
    """Manages all Google Sheets operations for billing."""

    SHEET_NAMES = {"Bills": "Bills", "Settings": "Settings"}

    # Column indices (0-based)
    COL_TIMESTAMP = 0
    COL_BILL_NO = 1
    COL_CUSTOMER = 2
    COL_PHONE = 3
    COL_ITEMS = 4
    COL_TOTAL = 5
    COL_PAID = 6
    COL_CHANGE = 7
    COL_PAYMENT = 8
    COL_STATUS = 9
    COL_DELETED_AT = 10

    def __init__(self, sheet_id: str, credentials_path: str):
        self.sheet_id = sheet_id
        self.credentials_path = credentials_path
        self.client = self._get_client()
        self.sh = self.client.open_by_key(sheet_id)
        self._ensure_sheets()

    def _get_client(self):
        creds = Credentials.from_service_account_file(
            self.credentials_path, scopes=SCOPES
        )
        return gspread.authorize(creds)

    def _ensure_sheets(self):
        """Create required worksheets and columns if they don't exist."""
        existing = [ws.title for ws in self.sh.worksheets()]

        # Bills sheet
        if "Bills" not in existing:
            ws = self.sh.add_worksheet("Bills", 1000, 12)
            ws.append_row(
                ["Timestamp", "Bill No", "Customer Name", "Phone", "Items",
                 "Total", "Paid", "Change", "Payment Type", "Status", "Deleted At"]
            )
        else:
            # Ensure status column exists
            ws = self.sh.worksheet("Bills")
            header = ws.row_values(1)
            if len(header) <= self.COL_STATUS:
                # Add Status header
                ws.update_cell(1, self.COL_STATUS + 1, "Status")
                # Fill existing rows with "active"
                all_rows = ws.get_all_values()
                for i in range(2, len(all_rows) + 1):
                    ws.update_cell(i, self.COL_STATUS + 1, "active")
            if len(header) <= self.COL_DELETED_AT:
                ws.update_cell(1, self.COL_DELETED_AT + 1, "Deleted At")

        # Settings sheet
        if "Settings" not in existing:
            ws = self.sh.add_worksheet("Settings", 10, 2)
            ws.append_row(["Key", "Value"])

    def _row_to_dict(self, row: list) -> dict:
        """Convert a sheet row to a dict, handling shorter rows."""
        def safe_get(idx, default=""):
            return row[idx] if len(row) > idx else default

        return {
            "timestamp": safe_get(self.COL_TIMESTAMP),
            "bill_no": safe_get(self.COL_BILL_NO),
            "customer": safe_get(self.COL_CUSTOMER),
            "phone": safe_get(self.COL_PHONE),
            "items": safe_get(self.COL_ITEMS),
            "total": safe_get(self.COL_TOTAL),
            "paid": safe_get(self.COL_PAID),
            "change": safe_get(self.COL_CHANGE),
            "payment_type": safe_get(self.COL_PAYMENT),
            "status": safe_get(self.COL_STATUS, "active"),
            "deleted_at": safe_get(self.COL_DELETED_AT, ""),
        }

    def add_bill(
        self,
        customer_name: str,
        phone: str,
        items: list[dict],
        total: float,
        paid: float,
        payment_type: str,
    ) -> int:
        """Add a new bill to the Bills sheet. Returns the bill number."""
        ws = self.sh.worksheet("Bills")
        change = round(paid - total, 2)
        bill_no = self._next_bill_number()

        items_str = ", ".join(
            f"{i['qty']}x {i['name']}={i['price']}" for i in items
        )

        ws.append_row(
            [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                bill_no,
                customer_name.strip(),
                phone.strip(),
                items_str,
                round(total, 2),
                round(paid, 2),
                change,
                payment_type,
                "active",
                "",
            ]
        )
        return bill_no

    def _next_bill_number(self) -> int:
        ws = self.sh.worksheet("Bills")
        records = ws.get_all_values()
        if len(records) <= 1:
            return 1
        max_no = 0
        for row in records[1:]:
            if row and len(row) > self.COL_BILL_NO and row[self.COL_BILL_NO].strip().isdigit():
                max_no = max(max_no, int(row[self.COL_BILL_NO]))
        return max_no + 1

    def _find_row_by_bill_no(self, bill_no: int) -> Optional[int]:
        """Find the row number (1-indexed) of a bill by its bill_no. Returns None if not found."""
        ws = self.sh.worksheet("Bills")
        records = ws.get_all_values()
        for i, row in enumerate(records[1:], start=2):
            if row and len(row) > self.COL_BILL_NO and row[self.COL_BILL_NO].strip() == str(bill_no):
                return i
        return None

    def delete_bill(self, bill_no: int) -> bool:
        """Soft-delete a bill: set Status to 'deleted' and record Deleted At timestamp."""
        row_idx = self._find_row_by_bill_no(bill_no)
        if row_idx is None:
            return False
        ws = self.sh.worksheet("Bills")
        ws.update_cell(row_idx, self.COL_STATUS + 1, "deleted")
        ws.update_cell(row_idx, self.COL_DELETED_AT + 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return True

    def edit_bill(self, bill_no: int, **updates) -> bool:
        """Edit a bill's fields. Accepts: customer_name, phone, items, total, paid, payment_type."""
        row_idx = self._find_row_by_bill_no(bill_no)
        if row_idx is None:
            return False
        ws = self.sh.worksheet("Bills")

        col_map = {
            "customer_name": self.COL_CUSTOMER,
            "phone": self.COL_PHONE,
            "items": self.COL_ITEMS,
            "total": self.COL_TOTAL,
            "paid": self.COL_PAID,
            "payment_type": self.COL_PAYMENT,
        }

        for key, value in updates.items():
            if key in col_map:
                ws.update_cell(row_idx, col_map[key] + 1, value)
        return True

    def get_today_earnings(self) -> float:
        """Sum of all non-deleted bills created today."""
        ws = self.sh.worksheet("Bills")
        records = ws.get_all_values()
        if len(records) <= 1:
            return 0.0
        today = datetime.now().strftime("%Y-%m-%d")
        total = 0.0
        for row in records[1:]:
            if len(row) <= self.COL_TOTAL:
                continue
            status = row[self.COL_STATUS] if len(row) > self.COL_STATUS else "active"
            if status == "deleted":
                continue
            if row[self.COL_TIMESTAMP].startswith(today):
                try:
                    total += float(row[self.COL_TOTAL])
                except (ValueError, IndexError):
                    continue
        return round(total, 2)

    def get_today_earnings_by_payment(self) -> dict:
        """Earnings split by payment type for today."""
        ws = self.sh.worksheet("Bills")
        records = ws.get_all_values()
        if len(records) <= 1:
            return {"Cash": 0.0, "UPI": 0.0}
        today = datetime.now().strftime("%Y-%m-%d")
        result = {"Cash": 0.0, "UPI": 0.0}
        for row in records[1:]:
            if len(row) <= self.COL_PAYMENT:
                continue
            status = row[self.COL_STATUS] if len(row) > self.COL_STATUS else "active"
            if status == "deleted":
                continue
            if row[self.COL_TIMESTAMP].startswith(today):
                try:
                    amount = float(row[self.COL_TOTAL])
                    ptype = row[self.COL_PAYMENT].strip()
                    if ptype in result:
                        result[ptype] += amount
                except (ValueError, IndexError):
                    continue
        return {k: round(v, 2) for k, v in result.items()}

    def get_recent_bills(self, limit: int = 10) -> list[dict]:
        """Get the most recent bills (active first, then deleted)."""
        ws = self.sh.worksheet("Bills")
        records = ws.get_all_values()
        if len(records) <= 1:
            return []

        active = []
        deleted = []
        for row in records[1:]:
            if len(row) <= self.COL_PAYMENT:
                continue
            d = self._row_to_dict(row)
            if d["status"] == "deleted":
                deleted.append(d)
            else:
                active.append(d)

        # Active newest first, then deleted
        active.sort(key=lambda b: int(b["bill_no"]) if b["bill_no"].isdigit() else 0, reverse=True)
        deleted.sort(key=lambda b: int(b["bill_no"]) if b["bill_no"].isdigit() else 0, reverse=True)

        return (active + deleted)[:limit]

    def get_all_bills(self) -> list[list]:
        """Get all bill records for backup/export."""
        ws = self.sh.worksheet("Bills")
        return ws.get_all_values()

    def get_setting(self, key: str) -> Optional[str]:
        """Get a setting from the Settings sheet."""
        try:
            ws = self.sh.worksheet("Settings")
            records = ws.get_all_values()
            for row in records[1:]:
                if row and row[0] == key:
                    return row[1] if len(row) > 1 else None
        except Exception:
            return None
        return None

    def set_setting(self, key: str, value: str):
        """Set a key-value pair in Settings sheet."""
        ws = self.sh.worksheet("Settings")
        records = ws.get_all_values()
        for i, row in enumerate(records[1:], start=2):
            if row and row[0] == key:
                ws.update_cell(i, 2, value)
                return
        ws.append_row([key, value])

    def search_bills(self, query: str) -> list[dict]:
        """Search bills by customer name or phone."""
        ws = self.sh.worksheet("Bills")
        records = ws.get_all_values()
        if len(records) <= 1:
            return []
        q = query.lower().strip()
        result = []
        for row in records[1:]:
            if len(row) <= self.COL_CUSTOMER:
                continue
            d = self._row_to_dict(row)
            if q in d["customer"].lower() or q in d["phone"]:
                result.append(d)
        return result
