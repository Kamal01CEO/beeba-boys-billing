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
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert "default-src 'self'" in resp.headers["Content-Security-Policy"]

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

        phone = client.post("/settings", data={"key": "shop_contact", "value": "+91 98765 43210"})
        assert phone.status_code == 200
        assert client.get("/settings/shop_contact").get_json()["value"] == "+91 98765 43210"

    def test_earnings_period_selector(self, client, local_storage):
        local_storage.add_bill("A", "1", [{"name": "Shirt", "qty": 1, "price": 500}], 500, 500, "Cash")
        response = client.get("/earnings?range=7d")
        assert response.status_code == 200
        data = response.get_json()
        assert data["period"] == "7d"
        assert data["period_label"] == "Last 7 days"
        assert data["cash"] == 500
        invalid = client.get("/earnings?range=forever")
        assert invalid.status_code == 400

    def test_delete_bill_actual(self, client, local_storage):
        """POST /delete-bill works for an existing bill."""
        # First add a bill via the storage
        bn = local_storage.add_bill("Test", "9999", [{"name": "X", "qty": 1, "price": 100}], 100, 100, "Cash")
        resp = client.post(f"/delete-bill/{bn}")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True

    def test_debit_account_purchase_and_payment_flow(self, client, local_storage, mocker):
        mocker.patch("app.routes.dashboard.get_printer", return_value=None)
        response = client.post("/generate-bill", data={
            "customer_name": "Kamal", "phone": "98765", "payment_type": "Debit",
            "item_name[]": ["Shirt"], "item_qty[]": ["1"], "item_price[]": ["500"],
        })
        assert response.status_code == 200
        assert response.get_json()["balance"] == 500
        assert response.get_json()["print_requested"] is False

        accounts = client.get("/debits").get_json()
        assert accounts["total_outstanding"] == 500
        account_id = accounts["accounts"][0]["account_id"]

        payment = client.post(f"/debits/{account_id}/payments", json={
            "amount": 200, "payment_method": "UPI", "note": "Partial",
        })
        assert payment.status_code == 200
        assert payment.get_json()["payment"]["balance"] == 300
        detail = client.get(f"/debits/{account_id}").get_json()["account"]
        assert detail["balance"] == 300
        assert len(detail["transactions"]) == 2

    def test_dashboard_discount_is_calculated_server_side(self, client, local_storage, mocker):
        mocker.patch("app.routes.dashboard.get_printer", return_value=None)
        response = client.post("/generate-bill", data={
            "customer_name": "Discount Customer", "payment_type": "Cash",
            "discount_percent": "15",
            "item_name[]": ["Shirt"], "item_qty[]": ["2"], "item_price[]": ["500"],
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data["subtotal"] == 1000
        assert data["discount_percent"] == 15
        assert data["discount_amount"] == 150
        assert data["total"] == 850
        assert client.get("/earnings").get_json()["cash"] == 850

    def test_debit_payment_rejects_overpayment(self, client, local_storage):
        purchase = local_storage.create_debit_purchase(
            "Kamal", "", [{"name": "Shirt", "qty": 1, "price": 500}], 500
        )
        response = client.post(f"/debits/{purchase['account_id']}/payments", json={
            "amount": 501, "payment_method": "Cash",
        })
        assert response.status_code == 400
        assert "cannot exceed" in response.get_json()["error"]


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

    def test_create_debit_bill_api(self, client, local_storage, mocker):
        mocker.patch("app.printer.PrinterManager.from_config_and_settings", return_value=None)
        response = client.post("/api/bill", json={
            "customer_name": "Kamal", "phone": "98765",
            "items": [{"name": "Shirt", "qty": 1, "price": 500}],
            "payment_type": "Debit",
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data["paid"] == 0
        assert data["balance"] == 500
        assert data["outstanding_debit"] == 500
        assert data["print_requested"] is False

    def test_api_discount_reduces_debit_balance(self, client, local_storage, mocker):
        mocker.patch("app.printer.PrinterManager.from_config_and_settings", return_value=None)
        response = client.post("/api/bill", json={
            "customer_name": "Kamal",
            "items": [{"name": "Jeans", "qty": 1, "price": 800}],
            "payment_type": "Debit", "discount_percent": 25,
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data["subtotal"] == 800
        assert data["discount_amount"] == 200
        assert data["total"] == 600
        assert data["balance"] == 600

    def test_earnings_local_storage_fallback(self, client, local_storage):
        """GET /api/earnings falls back to local storage."""
        resp = client.get("/api/earnings")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True

        ranged = client.get("/api/earnings?range=30d")
        assert ranged.status_code == 200
        assert ranged.get_json()["period"] == "30d"

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

    def test_debit_accounts_api(self, client, local_storage):
        purchase = local_storage.create_debit_purchase(
            "Riya", "90000", [{"name": "Jeans", "qty": 1, "price": 600}], 600
        )
        listing = client.get("/api/debits")
        assert listing.status_code == 200
        assert listing.get_json()["total_outstanding"] == 600
        payment = client.post(f"/api/debits/{purchase['account_id']}/payments", json={
            "amount": 600, "payment_method": "Cash",
        })
        assert payment.status_code == 200
        assert payment.get_json()["payment"]["balance"] == 0
