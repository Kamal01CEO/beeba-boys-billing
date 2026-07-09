"""Billing Software — MCP server exposing shop operations as agent tools (opencode/Claude)."""
from mcp.server.fastmcp import FastMCP

from app.storage import get_storage
from app.printer import PrinterManager
from app.analytics import today_stats
from app import billing_service

mcp = FastMCP("beeba-billing")


@mcp.tool()
def create_bill(customer_name: str, items: list, payment_type: str = "Cash", phone: str = "") -> dict:
    """Create a bill and auto-print it. items = [{"name","qty","price"}, ...]."""
    storage = get_storage()
    printer = PrinterManager.from_config_and_settings(storage)
    return billing_service.create_and_print(storage, printer, {
        "customer_name": customer_name, "phone": phone,
        "items": items, "payment_type": payment_type,
    })


@mcp.tool()
def today_earnings() -> dict:
    """Today's stats: total, cash, upi, bills, customers."""
    return today_stats(get_storage())


@mcp.tool()
def recent_bills(limit: int = 5) -> list:
    """Most recent bills (active first, then deleted)."""
    return get_storage().get_recent_bills(limit)


@mcp.tool()
def search_bills(query: str) -> list:
    """Search bills by customer name or phone."""
    return get_storage().search_bills(query)


if __name__ == "__main__":
    mcp.run()
