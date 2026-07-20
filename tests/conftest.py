"""Keep every test run isolated from the shop's real data directory."""
import app.local_storage as local_storage
import pytest


@pytest.fixture(autouse=True)
def isolated_shop_data(tmp_path, monkeypatch, request):
    data_dir = tmp_path / "shop-data"
    paths = {
        "DATA_DIR": data_dir,
        "BILLS_PATH": data_dir / "bills.json",
        "SETTINGS_PATH": data_dir / "settings.json",
        "DEBIT_PAYMENTS_PATH": data_dir / "debit_payments.json",
        "BACKUP_DIR": data_dir / "backups",
    }
    for name, value in paths.items():
        monkeypatch.setattr(local_storage, name, str(value))
        if hasattr(request.module, name):
            monkeypatch.setattr(request.module, name, str(value))
