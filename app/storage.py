"""Billing Software — storage backend selector (cached)."""
import os
from app.config import Config

_storage = None


def get_storage():
    global _storage
    if _storage is None:
        if os.path.exists(Config.SERVICE_ACCOUNT_PATH):
            from app.sheets import SheetsManager
            _storage = SheetsManager(Config.GOOGLE_SHEET_ID, Config.SERVICE_ACCOUNT_PATH)
        else:
            from app.excel_storage import ExcelStorage
            _storage = ExcelStorage()
    return _storage
