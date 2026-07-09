"""
Billing Software — Entry Point
"""
import logging
import threading
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("billing")


def start_flask():
    """Start the Flask web server."""
    from app import create_app
    from app.config import Config

    app = create_app()
    logger.info(
        f"Web UI starting at http://{Config.FLASK_HOST}:{Config.FLASK_PORT}"
    )
    app.run(host=Config.FLASK_HOST, port=Config.FLASK_PORT, debug=False)


def start_telegram():
    """Start the Telegram bot."""
    from app.config import Config
    from app.sheets import SheetsManager
    from app.printer import PrinterManager

    if not Config.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set. Telegram bot disabled.")
        return

    # Initialize sheets for the bot
    cred_path = Config.SERVICE_ACCOUNT_PATH
    if not os.path.exists(cred_path):
        logger.error(
            f"Service account file not found at {cred_path}. "
            "Telegram bot cannot start."
        )
        return

    sheets = SheetsManager(Config.GOOGLE_SHEET_ID, cred_path)
    printer = PrinterManager(Config.PRINTER_VENDOR_ID, Config.PRINTER_PRODUCT_ID)
    # Try to connect printer once (optional)
    printer.connect()
    printer.disconnect()

    from app.telegram_bot import BillBot

    bot = BillBot(
        token=Config.TELEGRAM_BOT_TOKEN,
        sheets_manager=sheets,
        printer_manager=printer,
        allowed_user_ids=Config.ALLOWED_USER_IDS,
        shop_name=Config.SHOP_NAME,
    )
    bot.run()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode == "web":
        start_flask()
    elif mode == "bot":
        start_telegram()
    elif mode == "all":
        # Run both in parallel
        flask_thread = threading.Thread(target=start_flask, daemon=True)
        flask_thread.start()
        start_telegram()
    else:
        print(f"Usage: python main.py [web|bot|all]")
        print("  web  - Start web dashboard only")
        print("  bot  - Start Telegram bot only")
        print("  all  - Start both (default)")
        sys.exit(1)
