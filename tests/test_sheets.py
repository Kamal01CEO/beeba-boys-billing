"""
Tests for Google Sheets module (mocked — no real API calls).
"""
import pytest
from app.sheets import SheetsManager


class TestSheetsManager:
    """Test SheetsManager with mocked gspread client."""

    @pytest.fixture(autouse=True)
    def mock_google_auth(self, mocker):
        """Mock Google auth to prevent real file reads."""
        mocker.patch(
            "google.oauth2.service_account.Credentials.from_service_account_file",
            return_value=mocker.MagicMock(),
        )
        mocker.patch("gspread.authorize", return_value=mocker.MagicMock())

    def _make_manager(self, mocker):
        """Helper to create a manager with mocked internals."""
        mock_sh = mocker.MagicMock()
        mock_ws = mocker.MagicMock()
        mock_client = mocker.MagicMock()
        mock_client.open_by_key.return_value = mock_sh

        mgr = SheetsManager("test-id", "/fake/path.json")
        mgr.sh = mock_sh
        mgr.client = mock_client
        mgr._get_client = lambda: mock_client
        mgr._ensure_sheets = lambda: None
        return mgr, mock_sh, mock_ws

    def test_next_bill_number_starts_at_1(self, mocker):
        """When Bills sheet has only header, next bill is 1."""
        mgr, mock_sh, mock_ws = self._make_manager(mocker)
        mock_ws.get_all_values.return_value = [["Timestamp", "Bill No", "Customer"]]
        mock_sh.worksheet.return_value = mock_ws

        result = mgr._next_bill_number()
        assert result == 1

    def test_next_bill_number_increments(self, mocker):
        """Next bill number is max existing + 1."""
        mgr, mock_sh, mock_ws = self._make_manager(mocker)
        mock_ws.get_all_values.return_value = [
            ["Timestamp", "Bill No", "Customer"],
            ["2025-01-01", "1", "Ram"],
            ["2025-01-02", "2", "Shyam"],
            ["2025-01-03", "3", "Hari"],
        ]
        mock_sh.worksheet.return_value = mock_ws

        result = mgr._next_bill_number()
        assert result == 4

    def test_add_bill_calls_append(self, mocker):
        """add_bill appends a row to the worksheet."""
        mgr, mock_sh, mock_ws = self._make_manager(mocker)
        mock_ws.get_all_values.return_value = [
            ["Timestamp", "Bill No", "Customer", "Phone", "Items", "Total", "Paid", "Change", "Payment Type"]
        ]
        mock_sh.worksheet.return_value = mock_ws

        items = [{"name": "Shirt", "qty": 1, "price": 800}]
        bill_no = mgr.add_bill("Test Customer", "9876543210", items, 800, 800, "Cash")

        assert bill_no == 1
        mock_ws.append_row.assert_called_once()

    def test_get_today_earnings_empty(self, mocker):
        """Earnings is 0 when no bills exist."""
        mgr, mock_sh, mock_ws = self._make_manager(mocker)
        mock_ws.get_all_values.return_value = [
            ["Timestamp", "Bill No", "Customer", "Phone", "Items", "Total"]
        ]
        mock_sh.worksheet.return_value = mock_ws

        result = mgr.get_today_earnings()
        assert result == 0.0

    def test_search_bills_finds_by_name(self, mocker):
        """search_bills finds matching records by customer name."""
        mgr, mock_sh, mock_ws = self._make_manager(mocker)
        mock_ws.get_all_values.return_value = [
            ["Timestamp", "Bill No", "Customer", "Phone", "Items", "Total", "Paid", "Change", "Payment Type"],
            ["2025-01-01 10:00", "1", "Ramesh Kumar", "9812345678", "1x Shirt=800", "800", "800", "0", "Cash"],
            ["2025-01-02 11:00", "2", "Suresh", "9876543210", "1x Jeans=1500", "1500", "1500", "0", "UPI"],
        ]
        mock_sh.worksheet.return_value = mock_ws

        results = mgr.search_bills("ramesh")
        assert len(results) == 1
        assert results[0]["customer"] == "Ramesh Kumar"

    def test_get_today_earnings_by_payment(self, mocker):
        """Earnings split by payment type."""
        mgr, mock_sh, mock_ws = self._make_manager(mocker)
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        mock_ws.get_all_values.return_value = [
            ["Timestamp", "Bill No", "Customer", "Phone", "Items", "Total", "Paid", "Change", "Payment Type"],
            [f"{today} 10:00", "1", "Ram", "123", "1x Shirt=800", "800", "800", "0", "Cash"],
            [f"{today} 11:00", "2", "Shyam", "456", "1x Jeans=1500", "1500", "1500", "0", "UPI"],
        ]
        mock_sh.worksheet.return_value = mock_ws

        result = mgr.get_today_earnings_by_payment()
        assert result["Cash"] == 800.0
        assert result["UPI"] == 1500.0

    def test_get_recent_bills(self, mocker):
        """get_recent_bills returns latest entries."""
        mgr, mock_sh, mock_ws = self._make_manager(mocker)
        mock_ws.get_all_values.return_value = [
            ["Timestamp", "Bill No", "Customer", "Phone", "Items", "Total", "Paid", "Change", "Payment Type"],
            ["2025-01-01 10:00", "1", "Ram", "123", "Shirt", "800", "800", "0", "Cash"],
            ["2025-01-01 11:00", "2", "Shyam", "456", "Jeans", "1500", "1500", "0", "UPI"],
            ["2025-01-01 12:00", "3", "Hari", "789", "TShirt", "600", "600", "0", "Cash"],
        ]
        mock_sh.worksheet.return_value = mock_ws

        recent = mgr.get_recent_bills(2)
        assert len(recent) == 2
        assert recent[0]["bill_no"] == "3"  # Most recent first
        assert recent[1]["bill_no"] == "2"

    def test_no_bills_returns_empty(self, mocker):
        """get_recent_bills returns empty list when no data."""
        mgr, mock_sh, mock_ws = self._make_manager(mocker)
        mock_sh.worksheet.return_value = mock_ws

        for method in ["get_today_earnings", "get_recent_bills", "search_bills"]:
            if method == "get_today_earnings":
                mock_ws.get_all_values.return_value = [["Timestamp", "Bill No"]]
                assert mgr.get_today_earnings() == 0.0
            elif method == "get_recent_bills":
                mock_ws.get_all_values.return_value = [["Timestamp", "Bill No"]]
                assert mgr.get_recent_bills() == []
            elif method == "search_bills":
                mock_ws.get_all_values.return_value = [["Timestamp", "Bill No"]]
                assert mgr.search_bills("test") == []
