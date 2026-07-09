"""
Billing Software — Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
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
    PRINTER_VENDOR_ID = int(os.getenv("PRINTER_VENDOR_ID", "0x0416"), 16)
    PRINTER_PRODUCT_ID = int(os.getenv("PRINTER_PRODUCT_ID", "0x5011"), 16)

    # Server
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
