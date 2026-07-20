import json
import os
import zipfile

import pytest

import app.local_storage as ls
from app.local_storage import LocalStorage, StorageCorruptionError


def test_repeat_purchases_and_partial_payment_stay_on_one_customer():
    storage = LocalStorage()
    first = storage.create_debit_purchase(
        "Kamal", "98765", [{"name": "Shirt", "qty": 1, "price": 500}], 500
    )
    second = storage.create_debit_purchase(
        " kamal ", "98765", [{"name": "Jeans", "qty": 1, "price": 600}], 600
    )

    assert first["account_id"] == second["account_id"]
    account = storage.get_debit_account(first["account_id"])
    assert account["total_purchased"] == 1100
    assert account["balance"] == 1100
    assert account["purchases"] == 2

    payment = storage.record_debit_payment(first["account_id"], 700, "Cash", "Part payment")
    account = storage.get_debit_account(first["account_id"])
    assert payment["balance"] == 400
    assert account["total_paid"] == 700
    assert account["balance"] == 400
    assert len(account["transactions"]) == 3

    storage.record_debit_payment(first["account_id"], 400, "UPI", "Final payment")
    paid_account = storage.get_debit_account(first["account_id"])
    assert paid_account["balance"] == 0
    assert paid_account["status"] == "paid"


def test_debit_sale_is_not_collected_cash_but_repayment_is():
    storage = LocalStorage()
    purchase = storage.create_debit_purchase(
        "Riya", "91234", [{"name": "T-Shirt", "qty": 1, "price": 800}], 800
    )
    assert storage.get_today_earnings() == 0
    assert storage.get_today_earnings_by_payment() == {"Cash": 0.0, "UPI": 0.0}

    storage.record_debit_payment(purchase["account_id"], 300, "UPI")
    assert storage.get_today_earnings() == 300
    assert storage.get_today_earnings_by_payment() == {"Cash": 0.0, "UPI": 300.0}


def test_payment_cannot_exceed_outstanding_balance():
    storage = LocalStorage()
    purchase = storage.create_debit_purchase(
        "Aman", "", [{"name": "Shirt", "qty": 1, "price": 500}], 500
    )
    with pytest.raises(ValueError, match="cannot exceed"):
        storage.record_debit_payment(purchase["account_id"], 501, "Cash")
    assert not ls._load_json(ls.DEBIT_PAYMENTS_PATH, [])


def test_purchase_with_linked_payment_cannot_be_voided_into_negative_balance():
    storage = LocalStorage()
    purchase = storage.create_debit_purchase(
        "Aman", "", [{"name": "Shirt", "qty": 1, "price": 500}], 500
    )
    storage.record_debit_payment(purchase["account_id"], 100, "Cash")
    with pytest.raises(ValueError, match="cannot be voided"):
        storage.delete_bill(purchase["bill_no"])
    assert storage.get_debit_account(purchase["account_id"])["balance"] == 400


def test_json_save_is_valid_and_includes_structured_items():
    storage = LocalStorage()
    storage.create_debit_purchase(
        "Meera", "90000", [{"name": "Jeans", "qty": 2, "price": 750.25}], 1500.50
    )
    with open(ls.BILLS_PATH, encoding="utf-8") as handle:
        bill = json.load(handle)[0]
    assert bill["paid"] == 0
    assert bill["change"] == -1500.50
    assert bill["item_details"] == [{"name": "Jeans", "qty": 2, "price": 750.25}]


def test_manual_backup_contains_financial_source_files():
    storage = LocalStorage()
    purchase = storage.create_debit_purchase(
        "Kamal", "98765", [{"name": "Shirt", "qty": 1, "price": 500}], 500
    )
    storage.record_debit_payment(purchase["account_id"], 100, "Cash")
    backup_path = storage.create_backup("test")
    assert os.path.exists(backup_path)
    with zipfile.ZipFile(backup_path) as archive:
        assert set(archive.namelist()) >= {"bills.json", "debit_payments.json"}


def test_corrupt_financial_file_is_never_silently_overwritten():
    os.makedirs(ls.DATA_DIR, exist_ok=True)
    with open(ls.BILLS_PATH, "w", encoding="utf-8") as handle:
        handle.write("[damaged")
    storage = LocalStorage()
    with pytest.raises(StorageCorruptionError, match="was not overwritten"):
        storage.add_bill(
            "Kamal", "", [{"name": "Shirt", "qty": 1, "price": 500}],
            500, 500, "Cash",
        )
    with open(ls.BILLS_PATH, encoding="utf-8") as handle:
        assert handle.read() == "[damaged"
