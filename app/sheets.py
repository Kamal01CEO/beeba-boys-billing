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
        """Create required worksheets if they don't exist."""
        existing = [ws.title for ws in self.sh.worksheets()]
        if "Bills" not in existing:
            ws = self.sh.add_worksheet("Bills", 1000, 9)
            ws.append_row(
                [
                    "Timestamp",
                    "Bill No",
                    "Customer Name",
                    "Phone",
                    "Items",
                    "Total",
                    "Paid",
                    "Change",
                    "Payment Type",
                ]
            )
        if "Settings" not in existing:
            ws = self.sh.add_worksheet("Settings", 10, 2)
            ws.append_row(["Key", "Value"])

    def add_bill(
        self,
        customer_name: str,
        phone: str,
        items: list[dict],
        total: float,
        paid: float,
        payment_type: str,
    ) -> int:
        """
        Add a new bill to the Bills sheet.
        Returns the bill number.
        """
        ws = self.sh.worksheet("Bills")
        change = round(paid - total, 2)
        bill_no = self._next_bill_number()

        # Format items as readable string
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
            ]
        )
        return bill_no

    def _next_bill_number(self) -> int:
        ws = self.sh.worksheet("Bills")
        records = ws.get_all_values()
        # Skip header row
        if len(records) <= 1:
            return 1
        # Find the max bill number from existing records
        max_no = 0
        for row in records[1:]:
            if row and row[1].strip().isdigit():
                max_no = max(max_no, int(row[1]))
        return max_no + 1

    def get_today_earnings(self) -> float:
        """Sum of all bills created today."""
        ws = self.sh.worksheet("Bills")
        records = ws.get_all_values()
        if len(records) <= 1:
            return 0.0
        today = datetime.now().strftime("%Y-%m-%d")
        total = 0.0
        for row in records[1:]:
            if row and row[0].startswith(today):
                try:
                    total += float(row[5])
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
            if row and row[0].startswith(today):
                try:
                    amount = float(row[5])
                    ptype = row[8].strip()
                    if ptype in result:
                        result[ptype] += amount
                except (ValueError, IndexError):
                    continue
        return {k: round(v, 2) for k, v in result.items()}

    def get_recent_bills(self, limit: int = 5) -> list[dict]:
        """Get the most recent bills."""
        ws = self.sh.worksheet("Bills")
        records = ws.get_all_values()
        if len(records) <= 1:
            return []
        rows = records[1:]
        recent = rows[-limit:]
        recent.reverse()
        result = []
        for row in recent:
            if len(row) >= 9:
                result.append(
                    {
                        "timestamp": row[0],
                        "bill_no": row[1],
                        "customer": row[2],
                        "phone": row[3],
                        "items": row[4],
                        "total": row[5],
                        "paid": row[6],
                        "change": row[7],
                        "payment_type": row[8],
                    }
                )
        return result

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
            if len(row) >= 9:
                if q in row[2].lower() or q in row[3]:
                    result.append(
                        {
                            "timestamp": row[0],
                            "bill_no": row[1],
                            "customer": row[2],
                            "phone": row[3],
                            "items": row[4],
                            "total": row[5],
                            "paid": row[6],
                            "change": row[7],
                            "payment_type": row[8],
                        }
                    )
        return result
