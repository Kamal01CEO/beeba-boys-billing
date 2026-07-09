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
