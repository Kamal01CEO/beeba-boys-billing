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


def test_logo_makes_output_larger():
    with_logo = PrinterManager(print_logo=True).render_bill_bytes(**BILL)
    without = PrinterManager(print_logo=False).render_bill_bytes(**BILL)
    assert len(with_logo) > len(without)  # real logo at app/static/logo.png


def test_send_none_returns_false():
    assert PrinterManager(transport="none").send(b"x") is False


def test_send_usb_dispatch(mocker):
    dev = mocker.MagicMock()
    mocker.patch("escpos.printer.Usb", return_value=dev)
    assert PrinterManager(transport="usb").send(b"hello") is True
    dev._raw.assert_called_once_with(b"hello")


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
