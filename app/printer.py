"""Billing Software — thermal printer: render once (ESC/POS), dispatch to a transport."""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PrinterManager:
    """Renders a 58mm receipt to raw ESC/POS bytes and sends to a configurable transport."""

    def __init__(self, vendor_id: int = 0x0416, product_id: int = 0x5011,
                 transport: str = "usb", serial_port: str = "", baud: int = 9600,
                 windows_name: str = "", width_dots: int = 384, chars: int = 32,
                 print_logo: bool = True):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.transport = transport
        self.serial_port = serial_port
        self.baud = baud
        self.windows_name = windows_name
        self.width_dots = width_dots
        self.chars = chars
        self.print_logo = print_logo

    # ---- factories ----
    @classmethod
    def from_config(cls):
        from app.config import Config
        return cls(
            vendor_id=Config.PRINTER_VENDOR_ID, product_id=Config.PRINTER_PRODUCT_ID,
            transport=Config.PRINTER_TRANSPORT, serial_port=Config.PRINTER_SERIAL_PORT,
            baud=Config.PRINTER_BAUD, windows_name=Config.PRINTER_WINDOWS_NAME,
            width_dots=Config.PRINTER_WIDTH_DOTS, chars=Config.PRINTER_CHARS,
        )

    @classmethod
    def from_config_and_settings(cls, storage):
        pm = cls.from_config()
        try:
            t = storage.get_setting("printer_transport")
            if t:
                pm.transport = t
            for skey, attr in (("printer_windows_name", "windows_name"),
                               ("printer_serial_port", "serial_port")):
                v = storage.get_setting(skey)
                if v:
                    setattr(pm, attr, v)
        except Exception as e:
            logger.warning(f"Could not read printer settings: {e}")
        return pm

    # ---- render ----
    def render_bill_bytes(self, shop_name, shop_address, shop_contact, bill_no,
                          customer_name, phone, items, total, paid, payment_type,
                          footer="") -> bytes:
        from escpos.printer import Dummy
        d = Dummy()

        if self.print_logo:
            try:
                from app.receipt_logo import get_receipt_logo
                logo = get_receipt_logo(self.width_dots)
                if logo is not None:
                    d.set(align="center")
                    d.image(logo)
            except Exception as e:
                logger.warning(f"Logo skipped: {e}")

        change = round(paid - total, 2)
        d.set(align="center", bold=True, double_height=True, double_width=True)
        d.text(f"{shop_name}\n")
        d.set(align="center", bold=False, double_height=False, double_width=False)
        if shop_address:
            d.text(f"{shop_address}\n")
        if shop_contact:
            d.text(f"Tel: {shop_contact}\n")
        d.text("=" * self.chars + "\n")

        d.set(align="left")
        d.text(f"Bill No: {bill_no}\n")
        d.text(f"Date: {datetime.now().strftime('%d-%b-%Y %H:%M')}\n")
        d.text(f"Customer: {customer_name}\n")
        if phone:
            d.text(f"Phone: {phone}\n")
        d.text("-" * self.chars + "\n")

        d.set(bold=True)
        d.text(f"{'Item':<16}{'Qty':>4}{'Amt':>8}\n")
        d.set(bold=False)
        d.text("-" * self.chars + "\n")
        for item in items:
            name = str(item["name"])[:16]
            line_total = item["qty"] * item["price"]
            d.text(f"{name:<16}{item['qty']:>4}{line_total:>8.0f}\n")
        d.text("-" * self.chars + "\n")

        d.set(bold=True, double_height=True)
        d.set(align="right")
        d.text(f"Total: Rs {total:.0f}\n")
        d.set(bold=False, double_height=False)
        d.text(f"Paid: Rs {paid:.0f} ({payment_type})\n")
        if change >= 0:
            d.text(f"Change: Rs {change:.0f}\n")
        else:
            d.text(f"Due: Rs {abs(change):.0f}\n")

        d.set(align="center")
        d.text("=" * self.chars + "\n")
        if footer:
            d.text(f"{footer}\n")
        d.text("\n\n")
        d.cut()
        return d.output

    # ---- dispatch ----
    def send(self, raw: bytes) -> bool:
        t = (self.transport or "usb").lower()
        try:
            if t == "none":
                return False
            if t == "usb":
                from escpos.printer import Usb
                dev = Usb(self.vendor_id, self.product_id, timeout=5)
                dev._raw(raw)
                self._safe_close(dev)
                return True
            if t == "serial":
                from escpos.printer import Serial
                dev = Serial(self.serial_port, baudrate=self.baud, timeout=1)
                dev._raw(raw)
                self._safe_close(dev)
                return True
            if t == "windows":
                import win32print
                h = win32print.OpenPrinter(self.windows_name)
                try:
                    win32print.StartDocPrinter(h, 1, ("Bill", None, "RAW"))
                    win32print.StartPagePrinter(h)
                    win32print.WritePrinter(h, raw)
                    win32print.EndPagePrinter(h)
                    win32print.EndDocPrinter(h)
                finally:
                    win32print.ClosePrinter(h)
                return True
        except Exception as e:
            logger.warning(f"Print send failed ({t}): {e}")
            return False
        logger.warning(f"Unknown printer transport: {t}")
        return False

    @staticmethod
    def _safe_close(dev):
        try:
            dev.close()
        except Exception:
            pass

    def print_bill(self, **bill) -> bool:
        try:
            raw = self.render_bill_bytes(**bill)
        except Exception as e:
            logger.error(f"Receipt render failed: {e}")
            return False
        return self.send(raw)
