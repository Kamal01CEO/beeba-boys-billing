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
