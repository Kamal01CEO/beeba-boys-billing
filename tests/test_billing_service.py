import pytest
import app.local_storage as ls
from app.billing_service import create_and_print, print_debit_payment_receipt


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ls, "BILLS_PATH", str(tmp_path / "bills.json"))
    monkeypatch.setattr(ls, "SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(ls, "DEBIT_PAYMENTS_PATH", str(tmp_path / "debit_payments.json"))
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


def test_percentage_discount_calculates_and_persists_financial_breakdown(storage):
    res = create_and_print(storage, None, {
        "customer_name": "Ramesh",
        "items": [{"name": "Shirt", "qty": 2, "price": 799.99}],
        "payment_type": "Cash", "discount_percent": "12.5",
    })
    assert res["success"] is True
    assert res["subtotal"] == 1599.98
    assert res["discount_percent"] == 12.5
    assert res["discount_amount"] == 200.0
    assert res["total"] == 1399.98
    assert res["paid"] == 1399.98
    saved = storage.get_recent_bills(1)[0]
    assert saved["subtotal"] == 1599.98
    assert saved["discount_amount"] == 200.0


@pytest.mark.parametrize("discount", [-1, 100.01, "not-a-number", "NaN"])
def test_invalid_discount_is_rejected_without_creating_bill(storage, discount):
    res = create_and_print(storage, None, {
        "customer_name": "Ramesh",
        "items": [{"name": "Shirt", "qty": 1, "price": 500}],
        "discount_percent": discount,
    })
    assert res["success"] is False
    assert "Discount" in res["error"]
    assert storage.get_recent_bills(1) == []


def test_discount_reduces_debit_balance_and_is_sent_to_printer(storage, mocker):
    printer = mocker.MagicMock()
    printer.print_bill.return_value = True
    res = create_and_print(storage, printer, {
        "customer_name": "Kamal",
        "items": [{"name": "Jeans", "qty": 1, "price": 1000}],
        "payment_type": "Debit", "discount_percent": 10,
        "print_receipt": True,
    })
    assert res["total"] == 900
    assert res["balance"] == 900
    assert storage.get_total_outstanding() == 900
    printer.print_bill.assert_called_once()
    printed_bill = printer.print_bill.call_args.kwargs
    assert printed_bill["subtotal"] == 1000
    assert printed_bill["discount_percent"] == 10
    assert printed_bill["discount_amount"] == 100


def test_fully_discounted_pay_later_bill_is_rejected(storage):
    res = create_and_print(storage, None, {
        "customer_name": "Kamal",
        "items": [{"name": "Shirt", "qty": 1, "price": 500}],
        "payment_type": "Debit", "discount_percent": 100,
    })
    assert res["success"] is False
    assert "greater than zero" in res["error"]


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
    assert res["print_requested"] is True
    printer.print_bill.assert_called_once()
    saved = storage.get_recent_bills(1)[0]
    assert saved["printed"] is True
    assert saved["print_requested"] is True


def test_printer_exception_does_not_fail_bill(storage, mocker):
    printer = mocker.MagicMock()
    printer.print_bill.side_effect = Exception("offline")
    res = create_and_print(storage, printer, {
        "customer_name": "A", "items": [{"name": "Shirt", "qty": 1, "price": 100}],
    })
    assert res["success"] is True and res["printed"] is False


def test_debit_bill_records_zero_paid_and_due_balance(storage):
    result = create_and_print(storage, None, {
        "customer_name": "Kamal", "phone": "98765",
        "items": [{"name": "Shirt", "qty": 1, "price": 500}],
        "payment_type": "Debit",
    })
    assert result["success"] is True
    assert result["paid"] == 0
    assert result["print_requested"] is False
    assert result["printed"] is False
    assert result["balance"] == 500
    bill = storage.get_recent_bills(1)[0]
    assert bill["payment_type"] == "Debit"
    assert bill["paid"] == 0


def test_debit_bill_does_not_print_by_default(storage, mocker):
    printer = mocker.MagicMock()
    result = create_and_print(storage, printer, {
        "customer_name": "Kamal",
        "items": [{"name": "Shirt", "qty": 1, "price": 500}],
        "payment_type": "Debit",
    })
    assert result["print_requested"] is False
    assert result["printed"] is False
    printer.print_bill.assert_not_called()


def test_debit_bill_prints_when_explicitly_checked(storage, mocker):
    printer = mocker.MagicMock()
    printer.print_bill.return_value = True
    result = create_and_print(storage, printer, {
        "customer_name": "Kamal",
        "items": [{"name": "Jeans", "qty": 1, "price": 600}],
        "payment_type": "Debit",
        "print_receipt": True,
    })
    assert result["print_requested"] is True
    assert result["printed"] is True
    printer.print_bill.assert_called_once()


def test_cash_bill_can_be_saved_without_print_when_unchecked(storage, mocker):
    printer = mocker.MagicMock()
    result = create_and_print(storage, printer, {
        "customer_name": "Kamal",
        "items": [{"name": "Shirt", "qty": 1, "price": 500}],
        "payment_type": "Cash",
        "print_receipt": "false",
    })
    assert result["print_requested"] is False
    printer.print_bill.assert_not_called()


def test_received_debit_payment_prints_and_saves_tick(storage, mocker):
    purchase = storage.create_debit_purchase(
        "Kamal", "98765", [{"name": "Shirt", "qty": 1, "price": 500}], 500
    )
    payment = storage.record_debit_payment(purchase["account_id"], 200, "Cash")
    printer = mocker.MagicMock()
    printer.print_debit_payment.return_value = True
    assert print_debit_payment_receipt(storage, printer, payment) is True
    account = storage.get_debit_account(purchase["account_id"])
    saved_payment = next(tx for tx in account["transactions"] if tx["type"] == "payment")
    assert saved_payment["printed"] is True
    printer.print_debit_payment.assert_called_once()
