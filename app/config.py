"""
Billing Software — Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Storage
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "excel").strip().lower()
    # Google Sheets
    GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
    SERVICE_ACCOUNT_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "credentials",
        "service-account.json",
    )

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ALLOWED_USER_IDS = [
        int(x.strip())
        for x in os.getenv("ALLOWED_USER_IDS", "").split(",")
        if x.strip().isdigit()
    ]

    # Shop
    SHOP_NAME = os.getenv("SHOP_NAME", "My Shop")
    SHOP_ADDRESS = os.getenv("SHOP_ADDRESS", "")
    SHOP_CONTACT = os.getenv("SHOP_CONTACT", "")
    BILL_FOOTER = os.getenv("BILL_FOOTER", "Thank you! Visit again!")

    # Printer
    # ATPOS H-58BT identifies over USB as STMicroelectronics 0x0456:0x0808.
    PRINTER_VENDOR_ID = int(os.getenv("PRINTER_VENDOR_ID", "0x0456"), 16)
    PRINTER_PRODUCT_ID = int(os.getenv("PRINTER_PRODUCT_ID", "0x0808"), 16)
    PRINTER_USB_IN_ENDPOINT = int(os.getenv("PRINTER_USB_IN_ENDPOINT", "0x81"), 16)
    PRINTER_USB_OUT_ENDPOINT = int(os.getenv("PRINTER_USB_OUT_ENDPOINT", "0x03"), 16)
    PRINTER_USB_CHUNK_BYTES = int(os.getenv("PRINTER_USB_CHUNK_BYTES", "512"))
    PRINTER_USB_CHUNK_DELAY_MS = int(os.getenv("PRINTER_USB_CHUNK_DELAY_MS", "25"))
    PRINTER_USB_FINAL_DELAY_MS = int(os.getenv("PRINTER_USB_FINAL_DELAY_MS", "500"))
    PRINTER_TRANSPORT = os.getenv("PRINTER_TRANSPORT", "windows")
    PRINTER_SERIAL_PORT = os.getenv("PRINTER_SERIAL_PORT", "")
    PRINTER_BAUD = int(os.getenv("PRINTER_BAUD", "9600"))
    PRINTER_WINDOWS_NAME = os.getenv("PRINTER_WINDOWS_NAME", "")
    PRINTER_WIDTH_DOTS = int(os.getenv("PRINTER_WIDTH_DOTS", "384"))
    PRINTER_LOGO_WIDTH_DOTS = int(os.getenv("PRINTER_LOGO_WIDTH_DOTS", "144"))
    PRINTER_CHARS = int(os.getenv("PRINTER_CHARS", "42"))
    PRINTER_AUTO_CUT = os.getenv("PRINTER_AUTO_CUT", "false").strip().casefold() in {"1", "true", "yes", "on"}

    # Server
    FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
    FLASK_SERVER = os.getenv("FLASK_SERVER", "waitress").strip().lower()
