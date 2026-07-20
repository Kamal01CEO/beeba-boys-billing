"""Tests for PrinterManager (mocked transports — no hardware)."""
import sys
import pytest
from app.printer import PrinterManager

BILL = dict(
    shop_name="Beeba Boys", shop_address="Main Road", shop_contact="9876543210",
    bill_no=5, customer_name="Ramesh", phone="9812345678",
    items=[{"name": "Shirt", "qty": 2, "price": 800}],
    total=1600, paid=1600, payment_type="Cash", footer="Thank you!",
)


def test_render_returns_bytes_with_shop_name():
    pm = PrinterManager(print_logo=False)
    raw = pm.render_bill_bytes(**BILL)
    assert isinstance(raw, (bytes, bytearray))
    assert len(raw) > 0
    assert b"Beeba Boys" in raw


def test_discount_is_shown_on_receipt():
    pm = PrinterManager(print_logo=False)
    raw = pm.render_bill_bytes(
        **BILL, subtotal=2000, discount_percent=20, discount_amount=400
    )
    assert b"Subtotal: Rs 2000.00" in raw
    assert b"Discount (20%): -Rs 400.00" in raw
    assert b"Total: Rs 1600.00" in raw


def test_logo_makes_output_larger():
    with_logo = PrinterManager(print_logo=True).render_bill_bytes(**BILL)
    without = PrinterManager(print_logo=False).render_bill_bytes(**BILL)
    assert len(with_logo) > len(without)  # real logo at app/static/logo.png


def test_send_none_returns_false():
    assert PrinterManager(transport="none").send(b"x") is False


def test_send_usb_dispatch(mocker):
    dev = mocker.MagicMock()
    usb_cls = mocker.patch("escpos.printer.Usb", return_value=dev)
    assert PrinterManager(transport="usb").send(b"hello") is True
    usb_cls.assert_called_once_with(
        0x0456, 0x0808, timeout=5, in_ep=0x81, out_ep=0x03,
    )
    dev._raw.assert_called_once_with(b"hello")


def test_h58_usb_output_is_sent_in_paced_chunks(mocker):
    dev = mocker.MagicMock()
    mocker.patch("escpos.printer.Usb", return_value=dev)
    pm = PrinterManager(
        transport="usb", usb_chunk_bytes=64,
        usb_chunk_delay_ms=0, usb_final_delay_ms=0,
    )
    payload = b"x" * 130
    assert pm.send(payload) is True
    assert [call.args[0] for call in dev._raw.call_args_list] == [b"x" * 64, b"x" * 64, b"x" * 2]


def test_h58_receipt_feeds_for_manual_tear_without_cut_command():
    pm = PrinterManager(print_logo=False, auto_cut=False)
    raw = pm.render_bill_bytes(**BILL)
    assert b"\x1dV" not in raw
    assert raw.endswith(b"\n\n\n")


def test_compact_h58_receipt_uses_small_logo_payload():
    raw = PrinterManager(print_logo=True).render_bill_bytes(**BILL)
    assert len(raw) < 6000


def test_send_serial_dispatch(mocker):
    dev = mocker.MagicMock()
    mocker.patch("escpos.printer.Serial", return_value=dev)
    pm = PrinterManager(transport="serial", serial_port="COM5")
    assert pm.send(b"hello") is True
    dev._raw.assert_called_once_with(b"hello")


def test_send_windows_dispatch(mocker):
    win = mocker.MagicMock()
    win.OpenPrinter.return_value = 42
    mocker.patch.dict(sys.modules, {"win32print": win})
    pm = PrinterManager(transport="windows", windows_name="POS58")
    assert pm.send(b"raw") is True
    win.OpenPrinter.assert_called_once_with("POS58")
    win.WritePrinter.assert_called_once_with(42, b"raw")


def test_send_swallows_exceptions(mocker):
    mocker.patch("escpos.printer.Usb", side_effect=Exception("no device"))
    assert PrinterManager(transport="usb").send(b"x") is False


def test_print_bill_calls_send(mocker):
    pm = PrinterManager(transport="none", print_logo=False)
    spy = mocker.spy(pm, "send")
    assert pm.print_bill(**BILL) is False
    spy.assert_called_once()


def test_debit_payment_receipt_has_received_and_balance():
    pm = PrinterManager(transport="none", print_logo=False)
    raw = pm.render_debit_payment_bytes(
        shop_name="Beeba Boys", shop_address="", shop_contact="",
        customer_name="Kamal", phone="98765", payment_id="abcdef123456",
        amount=300, payment_method="Cash", previous_balance=1100,
        balance=800, note="Part payment", footer="Thank you",
    )
    assert b"DEBIT PAYMENT RECEIPT" in raw
    assert b"Received: Rs 300.00" in raw
    assert b"Balance Due: Rs 800.00" in raw
