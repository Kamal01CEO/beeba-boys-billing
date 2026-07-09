"""
Tests for Flask app routes (mocked backend).
"""
import pytest
import json
import os
from app import create_app
from app.local_storage import LocalStorage, BILLS_PATH, SETTINGS_PATH


class TestDashboardRoutes:
    """Test Flask dashboard routes."""

    @pytest.fixture(autouse=True)
    def clean_data(self):
        """Clean up data files before each test."""
        for p in [BILLS_PATH, SETTINGS_PATH]:
            if os.path.exists(p):
                os.remove(p)
        yield

    @pytest.fixture
    def app(self):
        app = create_app()
        app.config["TESTING"] = True
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    @pytest.fixture
    def local_storage(self, mocker):
        """Patch get_sheets to return a fresh LocalStorage instance."""
        storage = LocalStorage()
        mocker.patch("app.routes.dashboard.get_sheets", return_value=storage)
        return storage

    def test_index_returns_html(self, client):
        """GET / returns the dashboard page."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Billing Suite" in resp.data

    def test_earnings_local_storage_fallback(self, client, local_storage):
        """GET /earnings uses local storage."""
        resp = client.get("/earnings")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True
        assert data["total"] == 0.0

    def test_delete_bill_not_found(self, client, local_storage):
        """POST /delete-bill/999 returns 404 for non-existent bill."""
        resp = client.post("/delete-bill/999")
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert data["success"] is False

    def test_edit_bill_not_found(self, client, local_storage):
        """POST /edit-bill/999 returns 404 for non-existent bill."""
        resp = client.post("/edit-bill/999", data={"customer_name": "Test"})
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert data["success"] is False

    def test_settings_roundtrip(self, client, local_storage):
        """Settings set and get work via dashboard routes."""
        resp = client.post("/settings", data={"key": "test_key", "value": "test_val"})
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True

        resp = client.get("/settings/test_key")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["value"] == "test_val"

    def test_delete_bill_actual(self, client, local_storage):
        """POST /delete-bill works for an existing bill."""
        # First add a bill via the storage
        bn = local_storage.add_bill("Test", "9999", [{"name": "X", "qty": 1, "price": 100}], 100, 100, "Cash")
        resp = client.post(f"/delete-bill/{bn}")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True


class TestAPIRoutes:
    """Test REST API routes."""

    @pytest.fixture
    def app(self):
        app = create_app()
        app.config["TESTING"] = True
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    @pytest.fixture
    def local_storage(self, mocker):
        """Patch get_sheets in api.py to return a fresh LocalStorage."""
        from app.local_storage import LocalStorage
        storage = LocalStorage()
        mocker.patch("app.routes.api.get_sheets", return_value=storage)
        return storage

    def test_health(self, client):
        """GET /api/health returns OK."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "ok"

    def test_create_bill_no_body(self, client):
        """POST /api/bill without body returns 400."""
        resp = client.post("/api/bill", content_type="application/json")
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "error" in data

    def test_earnings_local_storage_fallback(self, client, local_storage):
        """GET /api/earnings falls back to local storage."""
        resp = client.get("/api/earnings")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True

    def test_delete_bill_api_not_found(self, client, local_storage):
        """DELETE /api/bill/999 returns 404 for non-existent bill."""
        resp = client.delete("/api/bill/999")
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert data["success"] is False

    def test_edit_bill_api_not_found(self, client, local_storage):
        """PUT /api/bill/999 returns 404 for non-existent bill."""
        resp = client.put("/api/bill/999", json={"customer_name": "Test"})
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert data["success"] is False

    def test_settings_api_roundtrip(self, client, local_storage):
        """Settings set and get work via API routes."""
        resp = client.post("/api/settings", json={"key": "api_key", "value": "api_val"})
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True

        resp = client.get("/api/settings/api_key")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["value"] == "api_val"
