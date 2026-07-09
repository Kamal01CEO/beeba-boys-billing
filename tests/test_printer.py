"""
Tests for Printer module (mocked — no real hardware).
"""
import pytest
from app.printer import PrinterManager


class TestPrinterManager:
    """Test PrinterManager with mocked USB backend."""

    def test_connect_failure_graceful(self, mocker):
        """Printer connection failure doesn't crash."""
        mocker.patch("escpos.printer.Usb", side_effect=Exception("No device found"))
        printer = PrinterManager(0x0416, 0x5011)
        result = printer.connect()
        assert result is False
        assert printer.is_connected is False

    def test_connect_success(self, mocker):
        """Printer connection succeeds."""
        mock_usb = mocker.patch("escpos.printer.Usb")
        printer = PrinterManager(0x0416, 0x5011)
        result = printer.connect()
        assert result is True
        assert printer.is_connected is True
        mock_usb.assert_called_once_with(0x0416, 0x5011, timeout=5)

    def test_print_bill_returns_false_when_not_connected(self, mocker):
        """print_bill returns False without a connection."""
        printer = PrinterManager()
        result = printer.print_bill(
            shop_name="Test", shop_address="", shop_contact="",
            bill_no=1, customer_name="Test", phone="123",
            items=[{"name": "Shirt", "qty": 1, "price": 800}],
            total=800, paid=800, payment_type="Cash",
        )
        assert result is False

    def test_print_bill_success(self, mocker):
        """print_bill calls printer methods in correct order."""
        mock_printer = mocker.MagicMock()
        mocker.patch("escpos.printer.Usb", return_value=mock_printer)

        printer = PrinterManager()
        printer.connect()

        result = printer.print_bill(
            shop_name="Beeba Boys",
            shop_address="Shop 1, Main Road",
            shop_contact="9876543210",
            bill_no=5,
            customer_name="Ramesh",
            phone="9812345678",
            items=[{"name": "Shirt", "qty": 2, "price": 800}],
            total=1600,
            paid=1600,
            payment_type="Cash",
            footer="Thank you!",
        )
        assert result is True

        # Verify printer methods called
        assert mock_printer.set.call_count >= 3
        assert mock_printer.text.call_count >= 5
        mock_printer.cut.assert_called_once()
        mock_printer.close.assert_not_called()

    def test_disconnect(self, mocker):
        """disconnect closes the printer."""
        mock_printer = mocker.MagicMock()
        mocker.patch("escpos.printer.Usb", return_value=mock_printer)

        printer = PrinterManager()
        printer.connect()
        printer.disconnect()

        mock_printer.close.assert_called_once()
        assert printer.is_connected is False
