"""
Billing Software — Local JSON Storage (Demo/Offline Mode)
Replaces Google Sheets with a local JSON file for testing.
"""
import json
import os
from datetime import datetime
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
BILLS_PATH = os.path.join(DATA_DIR, "bills.json")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(path: str, default: list | dict):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default
    return default


def _save_json(path: str, data):
    _ensure_dir()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


class LocalStorage:
    """Local JSON-based storage that mirrors SheetsManager API."""

    def add_bill(
        self,
        customer_name: str,
        phone: str,
        items: list[dict],
        total: float,
        paid: float,
        payment_type: str,
    ) -> int:
        bills = _load_json(BILLS_PATH, [])
        bill_no = self._next_bill_number()
        change = round(paid - total, 2)
        items_str = ", ".join(
            f"{i['qty']}x {i['name']}={i['price']}" for i in items
        )
        bills.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "bill_no": bill_no,
            "customer_name": customer_name.strip(),
            "phone": phone.strip(),
            "items": items_str,
            "total": round(total, 2),
            "paid": round(paid, 2),
            "change": change,
            "payment_type": payment_type,
            "status": "active",
            "deleted_at": "",
        })
        _save_json(BILLS_PATH, bills)
        return bill_no

    def _next_bill_number(self) -> int:
        bills = _load_json(BILLS_PATH, [])
        if not bills:
            return 1
        return max(b.get("bill_no", 0) for b in bills) + 1

    def delete_bill(self, bill_no: int) -> bool:
        """Soft-delete a bill by setting status to deleted."""
        bills = _load_json(BILLS_PATH, [])
        found = False
        for b in bills:
            if b.get("bill_no") == bill_no and b.get("status") != "deleted":
                b["status"] = "deleted"
                b["deleted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                found = True
                break
        if found:
            _save_json(BILLS_PATH, bills)
        return found

    def edit_bill(self, bill_no: int, **updates) -> bool:
        """Edit a bill's customer_name, phone, items, total, paid, payment_type."""
        bills = _load_json(BILLS_PATH, [])
        found = False
        for b in bills:
            if b.get("bill_no") == bill_no and b.get("status") != "deleted":
                for key in ("customer_name", "phone", "items", "total", "paid", "payment_type"):
                    if key in updates:
                        b[key] = updates[key]
                found = True
                break
        if found:
            _save_json(BILLS_PATH, bills)
        return found

    def get_today_earnings(self) -> float:
        bills = _load_json(BILLS_PATH, [])
        today = datetime.now().strftime("%Y-%m-%d")
        total = 0.0
        for b in bills:
            if b.get("status") == "deleted":
                continue
            if b.get("timestamp", "").startswith(today):
                total += float(b.get("total", 0))
        return round(total, 2)

    def get_today_earnings_by_payment(self) -> dict:
        bills = _load_json(BILLS_PATH, [])
        today = datetime.now().strftime("%Y-%m-%d")
        result = {"Cash": 0.0, "UPI": 0.0}
        for b in bills:
            if b.get("status") == "deleted":
                continue
            if b.get("timestamp", "").startswith(today):
                amt = float(b.get("total", 0))
                ptype = b.get("payment_type", "Cash")
                if ptype in result:
                    result[ptype] += amt
        return {k: round(v, 2) for k, v in result.items()}

    def _format_bill(self, b: dict) -> dict:
        return {
            "timestamp": b.get("timestamp", ""),
            "bill_no": str(b.get("bill_no", "")),
            "customer": b.get("customer_name", ""),
            "phone": b.get("phone", ""),
            "items": b.get("items", ""),
            "total": b.get("total", ""),
            "paid": b.get("paid", ""),
            "change": b.get("change", ""),
            "payment_type": b.get("payment_type", ""),
            "status": b.get("status", "active"),
            "deleted_at": b.get("deleted_at", ""),
        }

    def get_recent_bills(self, limit: int = 10) -> list[dict]:
        bills = _load_json(BILLS_PATH, [])
        # Active first, then deleted, sorted by bill_no desc
        active = [b for b in bills if b.get("status") != "deleted"]
        deleted = [b for b in bills if b.get("status") == "deleted"]
        active.sort(key=lambda b: b.get("bill_no", 0), reverse=True)
        deleted.sort(key=lambda b: b.get("bill_no", 0), reverse=True)
        combined = (active + deleted)[:limit]
        return [self._format_bill(b) for b in combined]

    def get_all_bills(self) -> list[list]:
        bills = _load_json(BILLS_PATH, [])
        header = ["Timestamp", "Bill No", "Customer Name", "Phone", "Items",
                  "Total", "Paid", "Change", "Payment Type", "Status", "Deleted At"]
        rows = [[
            b.get("timestamp", ""), str(b.get("bill_no", "")),
            b.get("customer_name", ""), b.get("phone", ""),
            b.get("items", ""), str(b.get("total", "")),
            str(b.get("paid", "")), str(b.get("change", "")),
            b.get("payment_type", ""), b.get("status", "active"),
            b.get("deleted_at", ""),
        ] for b in bills]
        return [header] + rows

    def search_bills(self, query: str) -> list[dict]:
        bills = _load_json(BILLS_PATH, [])
        q = query.lower().strip()
        result = []
        for b in bills:
            if q in b.get("customer_name", "").lower() or q in b.get("phone", ""):
                result.append(self._format_bill(b))
        return result

    def get_setting(self, key: str) -> Optional[str]:
        settings = _load_json(SETTINGS_PATH, {})
        return settings.get(key)

    def set_setting(self, key: str, value: str):
        settings = _load_json(SETTINGS_PATH, {})
        settings[key] = value
        _save_json(SETTINGS_PATH, settings)
