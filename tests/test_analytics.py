import pytest
import app.local_storage as ls
from app.analytics import today_stats
from datetime import datetime, timedelta


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


def test_earnings_summary_supports_all_dashboard_periods(storage):
    storage.add_bill("Today", "1", [{"name": "A", "qty": 1, "price": 100}], 100, 100, "Cash")
    storage.add_bill("Week", "2", [{"name": "B", "qty": 1, "price": 200}], 200, 200, "UPI")
    storage.add_bill("Month", "3", [{"name": "C", "qty": 1, "price": 300}], 300, 300, "Cash")
    storage.add_bill("Year", "4", [{"name": "D", "qty": 1, "price": 400}], 400, 400, "UPI")
    bills = ls._load_json(ls.BILLS_PATH, [])
    bills[1]["timestamp"] = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d %H:%M:%S")
    bills[2]["timestamp"] = (datetime.now() - timedelta(days=29)).strftime("%Y-%m-%d %H:%M:%S")
    bills[3]["timestamp"] = (datetime.now() - timedelta(days=364)).strftime("%Y-%m-%d %H:%M:%S")
    ls._save_json(ls.BILLS_PATH, bills)

    assert storage.get_earnings_summary(1)["total"] == 100
    assert storage.get_earnings_summary(7)["total"] == 300
    assert storage.get_earnings_summary(30)["total"] == 600
    year = storage.get_earnings_summary(365)
    assert year["total"] == 1000
    assert year["cash"] == 400
    assert year["upi"] == 600
    assert year["bills"] == 4
    assert year["customers"] == 4


def test_earnings_summary_includes_debit_repayments_not_debit_sales(storage):
    purchase = storage.create_debit_purchase(
        "Kamal", "999", [{"name": "Shirt", "qty": 1, "price": 500}], 500
    )
    storage.record_debit_payment(purchase["account_id"], 200, "Cash")
    summary = storage.get_earnings_summary(7)
    assert summary["total"] == 200
    assert summary["cash"] == 200
    assert summary["debit_sales"] == 500
