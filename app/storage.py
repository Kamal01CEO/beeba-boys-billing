"""Billing Software — storage backend selector (cached)."""
import os
from app.config import Config

_storage = None


def get_storage():
    global _storage
    if _storage is None:
        if Config.STORAGE_BACKEND == "google_sheets":
            if not Config.GOOGLE_SHEET_ID or not os.path.exists(Config.SERVICE_ACCOUNT_PATH):
                raise RuntimeError("Google Sheets storage requires GOOGLE_SHEET_ID and credentials/service-account.json")
            from app.sheets import SheetsManager
            _storage = SheetsManager(Config.GOOGLE_SHEET_ID, Config.SERVICE_ACCOUNT_PATH)
        elif Config.STORAGE_BACKEND == "excel":
            from app.excel_storage import ExcelStorage
            _storage = ExcelStorage()
            _storage.ensure_daily_backup()
        else:
            raise RuntimeError("STORAGE_BACKEND must be 'excel' or 'google_sheets'")
    return _storage
