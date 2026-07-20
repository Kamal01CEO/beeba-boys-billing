"""Billing Software — thermal printer: render once (ESC/POS), dispatch to a transport."""
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class PrinterManager:
    """Renders a 58mm receipt to raw ESC/POS bytes and sends to a configurable transport."""

    def __init__(self, vendor_id: int = 0x0456, product_id: int = 0x0808,
                 usb_in_endpoint: int = 0x81, usb_out_endpoint: int = 0x03,
                 usb_chunk_bytes: int = 512, usb_chunk_delay_ms: int = 25,
                 usb_final_delay_ms: int = 500,
                 transport: str = "usb", serial_port: str = "", baud: int = 9600,
                 windows_name: str = "", width_dots: int = 384, chars: int = 42,
                 print_logo: bool = True, logo_width_dots: int = 144,
                 auto_cut: bool = False):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.usb_in_endpoint = usb_in_endpoint
        self.usb_out_endpoint = usb_out_endpoint
        self.usb_chunk_bytes = max(64, usb_chunk_bytes)
        self.usb_chunk_delay = max(0, usb_chunk_delay_ms) / 1000
        self.usb_final_delay = max(0, usb_final_delay_ms) / 1000
        self.transport = transport
        self.serial_port = serial_port
        self.baud = baud
        self.windows_name = windows_name
        self.width_dots = width_dots
        self.chars = chars
        self.print_logo = print_logo
        self.logo_width_dots = min(max(64, logo_width_dots), width_dots)
        self.auto_cut = auto_cut

    # ---- factories ----
    @classmethod
    def from_config(cls):
        from app.config import Config
        return cls(
            vendor_id=Config.PRINTER_VENDOR_ID, product_id=Config.PRINTER_PRODUCT_ID,
            usb_in_endpoint=Config.PRINTER_USB_IN_ENDPOINT,
            usb_out_endpoint=Config.PRINTER_USB_OUT_ENDPOINT,
            usb_chunk_bytes=Config.PRINTER_USB_CHUNK_BYTES,
            usb_chunk_delay_ms=Config.PRINTER_USB_CHUNK_DELAY_MS,
            usb_final_delay_ms=Config.PRINTER_USB_FINAL_DELAY_MS,
            transport=Config.PRINTER_TRANSPORT, serial_port=Config.PRINTER_SERIAL_PORT,
            baud=Config.PRINTER_BAUD, windows_name=Config.PRINTER_WINDOWS_NAME,
            width_dots=Config.PRINTER_WIDTH_DOTS, chars=Config.PRINTER_CHARS,
            logo_width_dots=Config.PRINTER_LOGO_WIDTH_DOTS,
            auto_cut=Config.PRINTER_AUTO_CUT,
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

    def _render_logo(self, device) -> None:
        if not self.print_logo:
            return
        try:
            from app.receipt_logo import get_receipt_logo
            logo = get_receipt_logo(self.logo_width_dots)
            if logo is not None:
                device.set(align="center")
                # ESC * column mode is the most compatible bitmap command for this H-58BT.
                device.image(logo, impl="bitImageColumn")
        except Exception as e:
            logger.warning(f"Logo skipped: {e}")

    def _finish_receipt(self, device) -> None:
        device.set(font="b", align="center", bold=False, normal_textsize=True)
        if self.auto_cut:
            device.cut()
        else:
            device.text("\n\n\n")

    # ---- render ----
    def render_bill_bytes(self, shop_name, shop_address, shop_contact, bill_no,
                          customer_name, phone, items, total, paid, payment_type,
                          footer="", subtotal=None, discount_percent=0,
                          discount_amount=0) -> bytes:
        from escpos.printer import Dummy
        d = Dummy()

        self._render_logo(d)

        change = round(paid - total, 2)
        d.set(font="b", align="center", bold=True, normal_textsize=True)
        d.text(f"{shop_name}\n")
        d.set(font="b", align="center", bold=False, normal_textsize=True)
        if shop_address:
            d.text(f"{shop_address}\n")
        if shop_contact:
            d.text(f"Tel: {shop_contact}\n")
        d.text("=" * self.chars + "\n")

        d.set(font="b", align="left", normal_textsize=True)
        d.text(f"Bill: {bill_no}  {datetime.now().strftime('%d-%b-%y %H:%M')}\n")
        d.text(f"Customer: {customer_name}\n")
        if phone:
            d.text(f"Phone: {phone}\n")
        d.text("-" * self.chars + "\n")

        d.set(bold=True)
        d.text(f"{'Item':<24}{'Qty':>4}{'Amount':>12}\n")
        d.set(bold=False)
        d.text("-" * self.chars + "\n")
        for item in items:
            name = str(item["name"])[:24]
            line_total = item["qty"] * item["price"]
            d.text(f"{name:<24}{item['qty']:>4}{line_total:>12.2f}\n")
        d.text("-" * self.chars + "\n")

        subtotal = total if subtotal is None else subtotal
        if discount_amount > 0:
            d.set(align="right")
            d.text(f"Subtotal: Rs {subtotal:.2f}\n")
            d.text(f"Discount ({discount_percent:g}%): -Rs {discount_amount:.2f}\n")
        d.set(font="b", bold=True, normal_textsize=True, align="right")
        d.text(f"Total: Rs {total:.2f}\n")
        d.set(font="b", bold=False, normal_textsize=True)
        d.text(f"Paid: Rs {paid:.2f} ({payment_type})\n")
        if change >= 0:
            d.text(f"Change: Rs {change:.0f}\n")
        else:
            d.text(f"Due: Rs {abs(change):.0f}\n")

        d.set(align="center")
        d.text("=" * self.chars + "\n")
        if footer:
            d.text(f"{footer}\n")
        self._finish_receipt(d)
        return d.output

    # ---- dispatch ----
    def send(self, raw: bytes) -> bool:
        t = (self.transport or "usb").lower()
        try:
            if t == "none":
                return False
            if t == "usb":
                from escpos.printer import Usb
                dev = Usb(
                    self.vendor_id, self.product_id, timeout=5,
                    in_ep=self.usb_in_endpoint, out_ep=self.usb_out_endpoint,
                )
                for offset in range(0, len(raw), self.usb_chunk_bytes):
                    dev._raw(raw[offset:offset + self.usb_chunk_bytes])
                    if self.usb_chunk_delay:
                        time.sleep(self.usb_chunk_delay)
                if self.usb_final_delay:
                    time.sleep(self.usb_final_delay)
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

    def render_debit_payment_bytes(self, shop_name, shop_address, shop_contact,
                                   customer_name, phone, payment_id, amount,
                                   payment_method, previous_balance, balance,
                                   note="", footer="") -> bytes:
        from escpos.printer import Dummy
        d = Dummy()
        self._render_logo(d)
        d.set(font="b", align="center", bold=True, normal_textsize=True)
        d.text(f"{shop_name}\n")
        d.set(font="b", bold=False, normal_textsize=True)
        if shop_address:
            d.text(f"{shop_address}\n")
        if shop_contact:
            d.text(f"Tel: {shop_contact}\n")
        d.text("=" * self.chars + "\n")
        d.set(font="b", bold=True, normal_textsize=True)
        d.text("DEBIT PAYMENT RECEIPT\n")
        d.set(font="b", bold=False, align="left", normal_textsize=True)
        d.text(f"Receipt: {payment_id[:8].upper()}\n")
        d.text(f"Date: {datetime.now().strftime('%d-%b-%Y %H:%M')}\n")
        d.text(f"Customer: {customer_name}\n")
        if phone:
            d.text(f"Phone: {phone}\n")
        d.text("-" * self.chars + "\n")
        d.text(f"Previous Due: Rs {previous_balance:.2f}\n")
        d.set(font="b", bold=True, normal_textsize=True, align="right")
        d.text(f"Received: Rs {amount:.2f}\n")
        d.set(font="b", bold=False, normal_textsize=True)
        d.text(f"By: {payment_method}\n")
        d.text(f"Balance Due: Rs {balance:.2f}\n")
        if note:
            d.set(align="left")
            d.text(f"Note: {note[:80]}\n")
        d.set(align="center")
        d.text("=" * self.chars + "\n")
        if footer:
            d.text(f"{footer}\n")
        self._finish_receipt(d)
        return d.output

    def print_debit_payment(self, **payment) -> bool:
        try:
            raw = self.render_debit_payment_bytes(**payment)
        except Exception as e:
            logger.error(f"Debit payment receipt render failed: {e}")
            return False
        return self.send(raw)
