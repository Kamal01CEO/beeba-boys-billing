"""
Tests for LocalStorage data layer — simpler approach.
"""
import json
import pytest
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
BILLS_PATH = os.path.join(DATA_DIR, "bills.json")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")


def backup_and_restore(func):
    """Decorator: backup data files, run test, restore."""
    def wrapper(*args, **kwargs):
        # Backup existing data
        bills_backup = None
        settings_backup = None
        if os.path.exists(BILLS_PATH):
            with open(BILLS_PATH) as f:
                bills_backup = f.read()
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH) as f:
                settings_backup = f.read()

        # Clean state
        if os.path.exists(BILLS_PATH):
            os.remove(BILLS_PATH)
        if os.path.exists(SETTINGS_PATH):
            os.remove(SETTINGS_PATH)

        try:
            return func(*args, **kwargs)
        finally:
            # Restore
            if bills_backup:
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(BILLS_PATH, "w") as f:
                    f.write(bills_backup)
            elif os.path.exists(BILLS_PATH):
                os.remove(BILLS_PATH)
            if settings_backup:
                with open(SETTINGS_PATH, "w") as f:
                    f.write(settings_backup)
            elif os.path.exists(SETTINGS_PATH):
                os.remove(SETTINGS_PATH)
    return wrapper


class TestLocalStorage:
    def _make_storage(self):
        from app.local_storage import LocalStorage
        return LocalStorage()

    @backup_and_restore
    def test_add_bill_has_status_active(self):
        s = self._make_storage()
        bill_no = s.add_bill("Test", "9999999999", [{"name": "Shirt", "qty": 1, "price": 500}], 500, 500, "Cash")
        assert bill_no >= 1

        bills = json.load(open(BILLS_PATH))
        assert bills[-1]["status"] == "active"

    @backup_and_restore
    def test_delete_bill(self):
        s = self._make_storage()
        b1 = s.add_bill("Ramesh", "911", [{"name": "Shirt", "qty": 1, "price": 800}], 800, 800, "Cash")
        b2 = s.add_bill("Suresh", "912", [{"name": "Jeans", "qty": 1, "price": 1500}], 1500, 1500, "UPI")

        ok = s.delete_bill(b1)
        assert ok is True

        recent = s.get_recent_bills(10)
        deleted = [b for b in recent if b.get("status") == "deleted"]
        assert any(int(b["bill_no"]) == b1 for b in deleted)

        # Earnings excludes deleted
        assert s.get_today_earnings() == 1500

    @backup_and_restore
    def test_delete_nonexistent(self):
        s = self._make_storage()
        assert s.delete_bill(999) is False

    @backup_and_restore
    def test_edit_bill(self):
        s = self._make_storage()
        b1 = s.add_bill("Ramesh", "911", [{"name": "Shirt", "qty": 1, "price": 800}], 800, 800, "Cash")

        ok = s.edit_bill(b1, customer_name="Ramesh Updated", payment_type="UPI")
        assert ok is True

        recent = s.get_recent_bills(10)
        edited = [b for b in recent if b["bill_no"] == str(b1)]
        assert edited[0]["customer"] == "Ramesh Updated"
        assert edited[0]["payment_type"] == "UPI"

    @backup_and_restore
    def test_edit_nonexistent(self):
        s = self._make_storage()
        assert s.edit_bill(999, customer_name="Nope") is False

    @backup_and_restore
    def test_earnings_excludes_deleted(self):
        s = self._make_storage()
        b1 = s.add_bill("A", "", [{"name": "A", "qty": 1, "price": 100}], 100, 100, "Cash")
        b2 = s.add_bill("B", "", [{"name": "B", "qty": 1, "price": 200}], 200, 200, "UPI")
        b3 = s.add_bill("C", "", [{"name": "C", "qty": 1, "price": 300}], 300, 300, "Cash")

        assert s.get_today_earnings() == 600
        s.delete_bill(b1)
        assert s.get_today_earnings() == 500
        s.delete_bill(b2)
        assert s.get_today_earnings() == 300

    @backup_and_restore
    def test_recent_bills_order(self):
        s = self._make_storage()
        b1 = s.add_bill("A", "", [{"name": "A", "qty": 1, "price": 100}], 100, 100, "Cash")
        b2 = s.add_bill("B", "", [{"name": "B", "qty": 1, "price": 200}], 200, 200, "UPI")
        b3 = s.add_bill("C", "", [{"name": "C", "qty": 1, "price": 300}], 300, 300, "Cash")

        s.delete_bill(b2)
        recent = s.get_recent_bills(10)

        # Active should come first
        assert recent[0]["status"] != "deleted"
        assert recent[1]["status"] != "deleted"
        # Deleted at end
        assert recent[2]["status"] == "deleted"

    @backup_and_restore
    def test_settings(self):
        s = self._make_storage()
        s.set_setting("shop_name", "Test Shop")
        assert s.get_setting("shop_name") == "Test Shop"
        assert s.get_setting("nonexistent") is None

    @backup_and_restore
    def test_get_today_bills_excludes_deleted(self):
        s = self._make_storage()
        b1 = s.add_bill("A", "", [{"name": "Shirt", "qty": 1, "price": 100}], 100, 100, "Cash")
        b2 = s.add_bill("B", "", [{"name": "Jeans", "qty": 1, "price": 200}], 200, 200, "UPI")
        s.delete_bill(b1)
        today = s.get_today_bills()
        assert len(today) == 1
        assert today[0]["customer_name"] == "B"

    @backup_and_restore
    def test_search_includes_status(self):
        s = self._make_storage()
        b1 = s.add_bill("Ramesh", "911", [{"name": "X", "qty": 1, "price": 100}], 100, 100, "Cash")
        s.delete_bill(b1)
        results = s.search_bills("Ramesh")
        assert len(results) == 1
        assert results[0]["status"] == "deleted"
