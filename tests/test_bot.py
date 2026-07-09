"""
Tests for Telegram bot module (mocked — no real API).
"""
import pytest
from app.telegram_bot import BillBot


class TestBillBot:
    """Test BillBot item parsing and authorization."""

    def test_parse_items_simple(self):
        """Parse comma-separated items with equals sign."""
        bot = BillBot("test", None, None, [])
        items = bot._parse_items("1 Shirt=800, 1 Jeans=1500")
        assert len(items) == 2
        assert items[0] == {"name": "Shirt", "qty": 1, "price": 800.0}
        assert items[1] == {"name": "Jeans", "qty": 1, "price": 1500.0}

    def test_parse_items_with_command_prefix(self):
        """Parse items after /bill command."""
        bot = BillBot("test", None, None, [])
        items = bot._parse_items("/bill 2 Shirt=800, 1 T-Shirt=600")
        assert len(items) == 2
        assert items[0] == {"name": "Shirt", "qty": 2, "price": 800.0}
        assert items[1] == {"name": "T-Shirt", "qty": 1, "price": 600.0}

    def test_parse_items_default_qty(self):
        """Default quantity is 1 when not specified."""
        bot = BillBot("test", None, None, [])
        items = bot._parse_items("Shirt=800, Jeans=1500")
        assert len(items) == 2
        assert items[0]["qty"] == 1
        assert items[1]["qty"] == 1

    def test_parse_items_with_colon(self):
        """Parse items with colon separator."""
        bot = BillBot("test", None, None, [])
        items = bot._parse_items("1 Shirt: 800, 1 Jeans:1500")
        assert len(items) == 2
        assert items[0]["name"] == "Shirt"
        assert items[1]["name"] == "Jeans"

    def test_parse_items_without_qty(self):
        """Parse items without quantity prefix."""
        bot = BillBot("test", None, None, [])
        items = bot._parse_items("shirt 800, jeans 1500")
        assert len(items) == 2
        assert items[0]["name"] == "Shirt"
        assert items[0]["qty"] == 1

    def test_parse_items_empty(self):
        """Empty text returns empty list."""
        bot = BillBot("test", None, None, [])
        items = bot._parse_items("")
        assert items == []

    def test_parse_items_invalid(self):
        """Garbage text returns empty list."""
        bot = BillBot("test", None, None, [])
        items = bot._parse_items("hello world")
        assert items == []

    def test_authorization_empty_ids_allows_all(self):
        """Empty allowed_ids means everyone is authorized."""
        bot = BillBot("test", None, None, [])
        assert bot._is_authorized(12345) is True
        assert bot._is_authorized(0) is True

    def test_authorization_restricts(self):
        """Only specified IDs are authorized."""
        bot = BillBot("test", None, None, [101, 102])
        assert bot._is_authorized(101) is True
        assert bot._is_authorized(999) is False

    def test_parse_items_handles_newlines(self):
        """Items separated by newlines are parsed correctly."""
        bot = BillBot("test", None, None, [])
        items = bot._parse_items("1 Shirt=800\n1 Jeans=1500")
        assert len(items) == 2
        assert items[0]["name"] == "Shirt"
        assert items[1]["name"] == "Jeans"
