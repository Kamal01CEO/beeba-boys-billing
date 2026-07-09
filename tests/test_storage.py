import app.storage as storage_mod
from app.excel_storage import ExcelStorage


def test_get_storage_returns_excel_without_credentials(monkeypatch):
    storage_mod._storage = None
    monkeypatch.setattr("app.config.Config.SERVICE_ACCOUNT_PATH", "/nope/service-account.json")
    s = storage_mod.get_storage()
    assert isinstance(s, ExcelStorage)


def test_get_storage_is_cached(monkeypatch):
    storage_mod._storage = None
    monkeypatch.setattr("app.config.Config.SERVICE_ACCOUNT_PATH", "/nope/service-account.json")
    assert storage_mod.get_storage() is storage_mod.get_storage()
