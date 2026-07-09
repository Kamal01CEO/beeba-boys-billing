"""
Tests for Flask app routes (mocked backend).
"""
import pytest
import json
from app import create_app


class TestDashboardRoutes:
    """Test Flask dashboard routes."""

    @pytest.fixture
    def app(self):
        app = create_app()
        app.config["TESTING"] = True
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def test_index_returns_html(self, client):
        """GET / returns the dashboard page."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Billing Dashboard" in resp.data

    def test_earnings_local_storage_fallback(self, client, mocker):
        """GET /earnings falls back to local storage when no service account."""
        mocker.patch("os.path.exists", return_value=False)
        resp = client.get("/earnings")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True
        assert data["total"] == 0.0


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

    def test_earnings_no_sheets(self, client, mocker):
        """GET /api/earnings without creds returns error."""
        mocker.patch("os.path.exists", return_value=False)
        resp = client.get("/api/earnings")
        assert resp.status_code == 500
