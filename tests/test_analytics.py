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
