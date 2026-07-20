"""Billing Software — analytics/reporting (shared by dashboard, bot, MCP)."""
from datetime import datetime

PERIODS = {
    "today": (1, "Today"),
    "7d": (7, "Last 7 days"),
    "30d": (30, "Last 30 days"),
    "1y": (365, "Last 1 year"),
}


def period_stats(storage, period: str = "today") -> dict:
    if period not in PERIODS:
        raise ValueError("Period must be today, 7d, 30d, or 1y")
    days, label = PERIODS[period]
    if hasattr(storage, "get_earnings_summary"):
        result = storage.get_earnings_summary(days)
    else:
        if days != 1:
            raise ValueError("Selected reporting period is unavailable for this storage backend")
        result = today_stats(storage)
    return {**result, "period": period, "period_label": label}


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
