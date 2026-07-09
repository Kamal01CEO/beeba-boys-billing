"""
Billing Software — Thermal Printer Integration
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PrinterManager:
    """Manages thermal receipt printer via ESC/POS protocol."""

    def __init__(self, vendor_id: int = 0x0416, product_id: int = 0x5011):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.printer = None

    def connect(self) -> bool:
        """
        Connect to the thermal printer via USB.
        Returns True if connected successfully.
        """
        try:
            from escpos.printer import Usb

            self.printer = Usb(self.vendor_id, self.product_id, timeout=5)
            logger.info(f"Printer connected: {self.vendor_id:04x}:{self.product_id:04x}")
            return True
        except Exception as e:
            logger.warning(f"Printer connection failed: {e}")
            self.printer = None
            return False

    def disconnect(self):
        """Close printer connection."""
        if self.printer:
            try:
                self.printer.close()
            except Exception:
                pass
            self.printer = None

    @property
    def is_connected(self) -> bool:
        return self.printer is not None

    def print_bill(
        self,
        shop_name: str,
        shop_address: str,
        shop_contact: str,
        bill_no: int,
        customer_name: str,
        phone: str,
        items: list[dict],
        total: float,
        paid: float,
        payment_type: str,
        footer: str = "",
    ) -> bool:
        """
        Print a bill receipt on the thermal printer.
        Returns True if printed successfully.
        """
        if not self.printer:
            logger.error("Printer not connected")
            return False

        try:
            change = round(paid - total, 2)
            self.printer.set(align="center", bold=True, double_height=True, double_width=True)
            self.printer.text(f"{shop_name}\n")
            self.printer.set(align="center", bold=False, double_height=False, double_width=False)
            self.printer.text(f"{shop_address}\n")
            self.printer.text(f"Tel: {shop_contact}\n")
            self.printer.text("=" * 32 + "\n")

            # Bill header
            self.printer.set(align="left")
            self.printer.text(f"Bill No: {bill_no}\n")
            from datetime import datetime
            self.printer.text(f"Date: {datetime.now().strftime('%d-%b-%Y %H:%M')}\n")
            self.printer.text(f"Customer: {customer_name}\n")
            self.printer.text(f"Phone: {phone}\n")
            self.printer.text("-" * 32 + "\n")

            # Items header
            self.printer.set(bold=True)
            self.printer.text(f"{'Item':<16}{'Qty':>4}{'Amt':>8}\n")
            self.printer.set(bold=False)
            self.printer.text("-" * 32 + "\n")

            # Items
            for item in items:
                name = item["name"][:16]
                qty = item["qty"]
                price = item["price"]
                line_total = qty * price
                self.printer.text(f"{name:<16}{qty:>4}{line_total:>8.0f}\n")

            self.printer.text("-" * 32 + "\n")

            # Totals
            self.printer.set(bold=True, double_height=True)
            self.printer.set(align="right")
            self.printer.text(f"Total: Rs {total:.0f}\n")
            self.printer.set(bold=False, double_height=False)
            self.printer.text(f"Paid: Rs {paid:.0f} ({payment_type})\n")
            if change >= 0:
                self.printer.text(f"Change: Rs {change:.0f}\n")
            else:
                self.printer.text(f"Due: Rs {abs(change):.0f}\n")

            self.printer.set(align="center")
            self.printer.text("=" * 32 + "\n")

            # Footer
            if footer:
                self.printer.text(f"{footer}\n")

            self.printer.text("\n\n")
            self.printer.cut()
            logger.info(f"Bill #{bill_no} printed successfully")
            return True

        except Exception as e:
            logger.error(f"Print failed: {e}")
            return False
