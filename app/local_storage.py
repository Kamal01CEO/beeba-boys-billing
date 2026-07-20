"""Billing Software — durable local source files and customer debit ledger."""
import json
import os
import hashlib
import tempfile
import threading
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_data_dir() -> str:
    configured = os.getenv("BILLING_DATA_DIR", "").strip()
    if configured:
        return os.path.abspath(os.path.expanduser(configured))
    if os.name == "nt":
        local_app_data = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
        if local_app_data:
            return os.path.join(local_app_data, "Beeba Boys 1001", "data")
    return os.path.join(PROJECT_DIR, "data")


DATA_DIR = _default_data_dir()
BILLS_PATH = os.path.join(DATA_DIR, "bills.json")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
DEBIT_PAYMENTS_PATH = os.path.join(DATA_DIR, "debit_payments.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

_write_lock = threading.RLock()


class StorageCorruptionError(RuntimeError):
    pass


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(path: str, default: list | dict):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            raise StorageCorruptionError(
                f"Financial data file is damaged and was not overwritten: {path}"
            ) from exc
        except OSError as exc:
            raise RuntimeError(f"Could not read financial data file: {path}") from exc
    return default


@contextmanager
def _data_lock():
    """Serialize writes across Flask, Telegram, and separate MCP processes."""
    with _write_lock:
        _ensure_dir()
        lock_path = os.path.join(DATA_DIR, ".billing.lock")
        with open(lock_path, "a+b") as lock_file:
            if os.name == "nt":
                import msvcrt
                lock_file.seek(0, os.SEEK_END)
                if lock_file.tell() == 0:
                    lock_file.write(b"0")
                    lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _save_json(path: str, data):
    """Atomically replace a JSON file so a crash cannot leave half-written data."""
    _ensure_dir()
    directory = os.path.dirname(path) or DATA_DIR
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".billing-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _money(value) -> float:
    try:
        return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Amount must be a valid number") from None


def _normalise_phone(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def _normalise_name(name: str) -> str:
    return " ".join((name or "").casefold().split())


def _legacy_account_id(name: str, phone: str) -> str:
    identity = f"{_normalise_phone(phone)}|{_normalise_name(name)}"
    return "legacy-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]


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
        subtotal: float | None = None,
        discount_percent: float = 0,
        discount_amount: float = 0,
    ) -> int:
        if payment_type.casefold() == "debit":
            return self.create_debit_purchase(
                customer_name, phone, items, total,
                subtotal=subtotal, discount_percent=discount_percent,
                discount_amount=discount_amount,
            )["bill_no"]

        with _data_lock():
            bills = _load_json(BILLS_PATH, [])
            bill_no = self._next_bill_number(bills)
            total = _money(total)
            paid = _money(paid)
            change = _money(paid - total)
            bills.append(self._bill_record(
                bill_no, customer_name, phone, items, total, paid,
                payment_type, change=change, subtotal=subtotal,
                discount_percent=discount_percent, discount_amount=discount_amount,
            ))
            _save_json(BILLS_PATH, bills)
            return bill_no

    @staticmethod
    def _next_bill_number(bills: Optional[list] = None) -> int:
        bills = bills if bills is not None else _load_json(BILLS_PATH, [])
        if not bills:
            return 1
        return max(b.get("bill_no", 0) for b in bills) + 1

    @staticmethod
    def _bill_record(bill_no, customer_name, phone, items, total, paid,
                     payment_type, change=0, account_id="", subtotal=None,
                     discount_percent=0, discount_amount=0) -> dict:
        items_str = ", ".join(
            f"{i['qty']}x {i['name']}={_money(i['price'])}" for i in items
        )
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "bill_no": bill_no,
            "customer_name": customer_name.strip(),
            "phone": phone.strip(),
            "items": items_str,
            "item_details": [
                {"name": str(i["name"]).strip(), "qty": int(i["qty"]), "price": _money(i["price"])}
                for i in items
            ],
            "subtotal": _money(total if subtotal is None else subtotal),
            "discount_percent": _money(discount_percent),
            "discount_amount": _money(discount_amount),
            "total": _money(total),
            "paid": _money(paid),
            "change": _money(change),
            "payment_type": payment_type,
            "account_id": account_id,
            "print_requested": None,
            "printed": None,
            "status": "active",
            "deleted_at": "",
        }

    @staticmethod
    def _account_id_for_bill(bill: dict) -> str:
        return bill.get("account_id") or _legacy_account_id(
            bill.get("customer_name", ""), bill.get("phone", "")
        )

    def _find_account_id(self, bills: list[dict], customer_name: str, phone: str) -> str:
        wanted_phone = _normalise_phone(phone)
        wanted_name = _normalise_name(customer_name)
        debit_bills = [b for b in bills if str(b.get("payment_type", "")).casefold() == "debit"]
        if wanted_phone:
            for bill in debit_bills:
                if _normalise_phone(bill.get("phone", "")) == wanted_phone:
                    return self._account_id_for_bill(bill)
        for bill in debit_bills:
            if _normalise_name(bill.get("customer_name", "")) == wanted_name:
                return self._account_id_for_bill(bill)
        return uuid.uuid4().hex

    def create_debit_purchase(self, customer_name: str, phone: str,
                              items: list[dict], total: float, subtotal: float | None = None,
                              discount_percent: float = 0, discount_amount: float = 0) -> dict:
        """Create an itemised pay-later bill attached to one customer account."""
        customer_name = (customer_name or "").strip()
        if not customer_name:
            raise ValueError("Customer name is required for debit purchases")
        total = _money(total)
        if total <= 0:
            raise ValueError("Debit purchase total must be greater than zero")

        with _data_lock():
            bills = _load_json(BILLS_PATH, [])
            account_id = self._find_account_id(bills, customer_name, phone)
            bill_no = self._next_bill_number(bills)
            bills.append(self._bill_record(
                bill_no, customer_name, phone, items, total, 0,
                "Debit", change=-total, account_id=account_id, subtotal=subtotal,
                discount_percent=discount_percent, discount_amount=discount_amount,
            ))
            _save_json(BILLS_PATH, bills)
        return {"bill_no": bill_no, "account_id": account_id, "balance": self.get_debit_account(account_id)["balance"]}

    def record_debit_payment(self, account_id: str, amount: float,
                             payment_method: str, note: str = "") -> dict:
        """Append a repayment without rewriting or erasing the purchase history."""
        amount = _money(amount)
        if amount <= 0:
            raise ValueError("Payment amount must be greater than zero")
        method = (payment_method or "").strip().upper()
        if method not in {"CASH", "UPI"}:
            raise ValueError("Payment method must be Cash or UPI")

        with _data_lock():
            account = self.get_debit_account(account_id)
            if amount > account["balance"]:
                raise ValueError(f"Payment cannot exceed outstanding balance of ₹{account['balance']:.2f}")
            payments = _load_json(DEBIT_PAYMENTS_PATH, [])
            record = {
                "payment_id": uuid.uuid4().hex,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "account_id": account_id,
                "customer_name": account["customer_name"],
                "phone": account["phone"],
                "amount": amount,
                "payment_method": "UPI" if method == "UPI" else "Cash",
                "note": (note or "").strip(),
                "print_requested": True,
                "printed": False,
                "status": "active",
            }
            payments.append(record)
            _save_json(DEBIT_PAYMENTS_PATH, payments)

        record["balance"] = _money(account["balance"] - amount)
        return record

    def mark_bill_print_status(self, bill_no: int, requested: bool, printed: bool) -> bool:
        with _data_lock():
            bills = _load_json(BILLS_PATH, [])
            for bill in bills:
                if bill.get("bill_no") == bill_no:
                    bill["print_requested"] = bool(requested)
                    bill["printed"] = bool(printed)
                    _save_json(BILLS_PATH, bills)
                    return True
        return False

    def mark_debit_payment_print_status(self, payment_id: str, printed: bool) -> bool:
        with _data_lock():
            payments = _load_json(DEBIT_PAYMENTS_PATH, [])
            for payment in payments:
                if payment.get("payment_id") == payment_id:
                    payment["print_requested"] = True
                    payment["printed"] = bool(printed)
                    _save_json(DEBIT_PAYMENTS_PATH, payments)
                    return True
        return False

    def get_debit_accounts(self) -> list[dict]:
        bills = _load_json(BILLS_PATH, [])
        payments = _load_json(DEBIT_PAYMENTS_PATH, [])
        accounts: dict[str, dict] = {}

        for bill in bills:
            if bill.get("status") == "deleted" or str(bill.get("payment_type", "")).casefold() != "debit":
                continue
            account_id = self._account_id_for_bill(bill)
            account = accounts.setdefault(account_id, {
                "account_id": account_id,
                "customer_name": bill.get("customer_name", ""),
                "phone": bill.get("phone", ""),
                "purchases": 0,
                "total_purchased": 0.0,
                "total_paid": 0.0,
                "balance": 0.0,
                "last_activity": bill.get("timestamp", ""),
            })
            account["customer_name"] = bill.get("customer_name", "") or account["customer_name"]
            account["phone"] = bill.get("phone", "") or account["phone"]
            account["purchases"] += 1
            account["total_purchased"] = _money(account["total_purchased"] + _money(bill.get("total", 0)))
            account["last_activity"] = max(account["last_activity"], bill.get("timestamp", ""))

        for payment in payments:
            if payment.get("status", "active") != "active":
                continue
            account = accounts.get(payment.get("account_id"))
            if not account:
                continue
            account["total_paid"] = _money(account["total_paid"] + _money(payment.get("amount", 0)))
            account["last_activity"] = max(account["last_activity"], payment.get("timestamp", ""))

        for account in accounts.values():
            account["balance"] = _money(account["total_purchased"] - account["total_paid"])
            account["status"] = "paid" if account["balance"] == 0 else "outstanding"
        return sorted(accounts.values(), key=lambda a: (a["balance"] > 0, a["last_activity"]), reverse=True)

    def get_debit_account(self, account_id: str) -> dict:
        account = next((a for a in self.get_debit_accounts() if a["account_id"] == account_id), None)
        if not account:
            raise KeyError("Debit customer not found")

        timeline = []
        for bill in _load_json(BILLS_PATH, []):
            if bill.get("status") == "deleted" or str(bill.get("payment_type", "")).casefold() != "debit":
                continue
            if self._account_id_for_bill(bill) != account_id:
                continue
            timeline.append({
                "type": "purchase", "timestamp": bill.get("timestamp", ""),
                "bill_no": bill.get("bill_no"), "amount": _money(bill.get("total", 0)),
                "items": bill.get("items", ""), "item_details": bill.get("item_details", []),
                "subtotal": _money(bill.get("subtotal", bill.get("total", 0))),
                "discount_percent": _money(bill.get("discount_percent", 0)),
                "discount_amount": _money(bill.get("discount_amount", 0)),
                "print_requested": bill.get("print_requested"), "printed": bill.get("printed"),
            })
        for payment in _load_json(DEBIT_PAYMENTS_PATH, []):
            if payment.get("status", "active") != "active" or payment.get("account_id") != account_id:
                continue
            timeline.append({
                "type": "payment", "timestamp": payment.get("timestamp", ""),
                "payment_id": payment.get("payment_id"), "amount": _money(payment.get("amount", 0)),
                "payment_method": payment.get("payment_method", ""), "note": payment.get("note", ""),
                    "print_requested": payment.get("print_requested"),
                    "printed": payment.get("printed"),
            })
        account = dict(account)
        account["transactions"] = sorted(timeline, key=lambda entry: entry["timestamp"], reverse=True)
        return account

    def get_total_outstanding(self) -> float:
        return _money(sum(account["balance"] for account in self.get_debit_accounts()))

    def create_backup(self, reason: str = "manual") -> str:
        """Create a timestamped ZIP containing the financial source files."""
        os.makedirs(BACKUP_DIR, exist_ok=True)
        safe_reason = "".join(ch for ch in reason.casefold() if ch.isalnum() or ch in "-_ ").strip().replace(" ", "-")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = os.path.join(BACKUP_DIR, f"beeba-boys-{stamp}-{safe_reason or 'backup'}.zip")
        candidates = [BILLS_PATH, SETTINGS_PATH, DEBIT_PAYMENTS_PATH]
        xlsx_path = getattr(self, "xlsx_path", os.path.join(DATA_DIR, "bills.xlsx"))
        candidates.append(xlsx_path)
        with _data_lock():
            with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in candidates:
                    if os.path.exists(path):
                        archive.write(path, arcname=os.path.basename(path))
        return backup_path

    def ensure_daily_backup(self) -> Optional[str]:
        """Take at most one automatic backup per day when shop data exists."""
        if not any(os.path.exists(path) for path in (BILLS_PATH, SETTINGS_PATH, DEBIT_PAYMENTS_PATH)):
            return None
        today_prefix = f"beeba-boys-{datetime.now().strftime('%Y%m%d')}-"
        if os.path.isdir(BACKUP_DIR) and any(name.startswith(today_prefix) for name in os.listdir(BACKUP_DIR)):
            return None
        return self.create_backup("daily")

    def delete_bill(self, bill_no: int) -> bool:
        """Soft-delete a bill by setting status to deleted."""
        with _data_lock():
            bills = _load_json(BILLS_PATH, [])
            found = False
            for b in bills:
                if b.get("bill_no") == bill_no and b.get("status") != "deleted":
                    if str(b.get("payment_type", "")).casefold() == "debit":
                        account_id = self._account_id_for_bill(b)
                        active_purchases = sum(
                            _money(other.get("total", 0)) for other in bills
                            if other.get("status") != "deleted"
                            and str(other.get("payment_type", "")).casefold() == "debit"
                            and self._account_id_for_bill(other) == account_id
                        )
                        paid = sum(
                            _money(payment.get("amount", 0))
                            for payment in _load_json(DEBIT_PAYMENTS_PATH, [])
                            if payment.get("status", "active") == "active"
                            and payment.get("account_id") == account_id
                        )
                        if _money(active_purchases - _money(b.get("total", 0))) < _money(paid):
                            raise ValueError(
                                "This debit purchase cannot be voided because customer payments are already linked to it"
                            )
                    b["status"] = "deleted"
                    b["deleted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    found = True
                    break
            if found:
                _save_json(BILLS_PATH, bills)
            return found

    def edit_bill(self, bill_no: int, **updates) -> bool:
        """Edit a bill's customer_name, phone, items, total, paid, payment_type."""
        with _data_lock():
            bills = _load_json(BILLS_PATH, [])
            found = False
            for b in bills:
                if b.get("bill_no") == bill_no and b.get("status") != "deleted":
                    is_debit = str(b.get("payment_type", "")).casefold() == "debit"
                    if is_debit and any(key in updates for key in ("total", "paid", "payment_type")):
                        raise ValueError("Financial fields on a debit bill cannot be edited; void it and create a corrected bill")
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
                total += float(b.get("paid", b.get("total", 0)))
        for payment in _load_json(DEBIT_PAYMENTS_PATH, []):
            if payment.get("status", "active") == "active" and payment.get("timestamp", "").startswith(today):
                total += float(payment.get("amount", 0))
        return _money(total)

    def get_today_earnings_by_payment(self) -> dict:
        bills = _load_json(BILLS_PATH, [])
        today = datetime.now().strftime("%Y-%m-%d")
        result = {"Cash": 0.0, "UPI": 0.0}
        for b in bills:
            if b.get("status") == "deleted":
                continue
            if b.get("timestamp", "").startswith(today):
                amt = float(b.get("paid", b.get("total", 0)))
                ptype = b.get("payment_type", "Cash")
                if ptype in result:
                    result[ptype] += amt
        for payment in _load_json(DEBIT_PAYMENTS_PATH, []):
            if payment.get("status", "active") != "active" or not payment.get("timestamp", "").startswith(today):
                continue
            method = payment.get("payment_method", "")
            if method in result:
                result[method] += float(payment.get("amount", 0))
        return {k: _money(v) for k, v in result.items()}

    def get_earnings_summary(self, days: int = 1) -> dict:
        """Return collected Cash/UPI and bill counts for an inclusive date window."""
        if days not in {1, 7, 30, 365}:
            raise ValueError("Reporting period must be 1, 7, 30, or 365 days")
        today = datetime.now().date()
        cutoff = today - timedelta(days=days - 1)

        def in_period(record: dict) -> bool:
            try:
                record_date = datetime.strptime(str(record.get("timestamp", ""))[:10], "%Y-%m-%d").date()
            except ValueError:
                return False
            return cutoff <= record_date <= today

        cash = 0.0
        upi = 0.0
        debit_sales = 0.0
        bill_count = 0
        customers: set[str] = set()
        for bill in _load_json(BILLS_PATH, []):
            if bill.get("status") == "deleted" or not in_period(bill):
                continue
            bill_count += 1
            identity = _normalise_phone(bill.get("phone", "")) or _normalise_name(bill.get("customer_name", ""))
            if identity:
                customers.add(identity)
            payment_type = str(bill.get("payment_type", "Cash"))
            amount = _money(bill.get("paid", bill.get("total", 0)))
            if payment_type == "Cash":
                cash += amount
            elif payment_type == "UPI":
                upi += amount
            elif payment_type.casefold() == "debit":
                debit_sales += _money(bill.get("total", 0))

        for payment in _load_json(DEBIT_PAYMENTS_PATH, []):
            if payment.get("status", "active") != "active" or not in_period(payment):
                continue
            amount = _money(payment.get("amount", 0))
            if payment.get("payment_method") == "Cash":
                cash += amount
            elif payment.get("payment_method") == "UPI":
                upi += amount

        cash = _money(cash)
        upi = _money(upi)
        return {
            "days": days,
            "total": _money(cash + upi),
            "cash": cash,
            "upi": upi,
            "debit_sales": _money(debit_sales),
            "bills": bill_count,
            "customers": len(customers),
        }

    def get_today_bills(self) -> list[dict]:
        bills = _load_json(BILLS_PATH, [])
        today = datetime.now().strftime("%Y-%m-%d")
        return [
            b for b in bills
            if b.get("status") != "deleted" and b.get("timestamp", "").startswith(today)
        ]

    def _format_bill(self, b: dict) -> dict:
        return {
            "timestamp": b.get("timestamp", ""),
            "bill_no": str(b.get("bill_no", "")),
            "customer": b.get("customer_name", ""),
            "phone": b.get("phone", ""),
            "items": b.get("items", ""),
            "subtotal": b.get("subtotal", b.get("total", "")),
            "discount_percent": b.get("discount_percent", 0),
            "discount_amount": b.get("discount_amount", 0),
            "total": b.get("total", ""),
            "paid": b.get("paid", ""),
            "change": b.get("change", ""),
            "payment_type": b.get("payment_type", ""),
            "status": b.get("status", "active"),
            "deleted_at": b.get("deleted_at", ""),
            "account_id": self._account_id_for_bill(b) if str(b.get("payment_type", "")).casefold() == "debit" else "",
            "print_requested": b.get("print_requested"),
            "printed": b.get("printed"),
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
                  "Subtotal", "Discount %", "Discount Amount", "Total", "Paid", "Change",
                  "Payment Type", "Status", "Deleted At"]
        rows = [[
            b.get("timestamp", ""), str(b.get("bill_no", "")),
            b.get("customer_name", ""), b.get("phone", ""),
            b.get("items", ""), str(b.get("subtotal", b.get("total", ""))),
            str(b.get("discount_percent", 0)), str(b.get("discount_amount", 0)),
            str(b.get("total", "")),
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
        with _data_lock():
            settings = _load_json(SETTINGS_PATH, {})
            settings[key] = value
            _save_json(SETTINGS_PATH, settings)
