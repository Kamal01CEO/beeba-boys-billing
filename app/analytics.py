"""Billing Software — analytics/reporting (shared by dashboard, bot, MCP)."""
from datetime import datetime


def today_stats(storage) -> dict:
    total = storage.get_today_earnings()
    by_pay = storage.get_today_earnings_by_payment()
    bills = len(storage.get_today_bills())
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total": total,
        "cash": by_pay.get("Cash", 0),
        "upi": by_pay.get("UPI", 0),
        "bills": bills,
        "customers": bills,
    }
