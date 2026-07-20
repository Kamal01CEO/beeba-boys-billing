"""Billing Software — single create+print path shared by web, API, bot, MCP."""
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from app.config import Config

logger = logging.getLogger("billing")


def _as_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "on", "checked"}


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def create_and_print(storage, printer, data: dict) -> dict:
    customer_name = (data.get("customer_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    raw_items = data.get("items") or []
    payment_type = str(data.get("payment_type") or "Cash").strip().title()

    if not customer_name:
        return {"success": False, "error": "customer_name is required"}
    if not raw_items:
        return {"success": False, "error": "At least one item is required"}
    if payment_type not in {"Cash", "Upi", "Debit"}:
        return {"success": False, "error": "Payment type must be Cash, UPI, or Debit"}
    if payment_type == "Upi":
        payment_type = "UPI"

    items = []
    try:
        for item in raw_items:
            name = str(item.get("name") or "").strip()
            qty = int(item.get("qty", 0))
            price = Decimal(str(item.get("price", 0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if not name or qty <= 0 or price <= 0:
                raise ValueError
            items.append({"name": name, "qty": qty, "price": float(price)})
    except (AttributeError, InvalidOperation, TypeError, ValueError):
        return {"success": False, "error": "Every item needs a name, positive quantity, and positive price"}

    subtotal_decimal = _money(sum(Decimal(i["qty"]) * Decimal(str(i["price"])) for i in items))
    raw_discount = data.get("discount_percent", 0)
    try:
        discount_percent_decimal = _money(Decimal(str(raw_discount or 0)))
    except (InvalidOperation, TypeError, ValueError):
        return {"success": False, "error": "Discount must be a number from 0 to 100"}
    if not discount_percent_decimal.is_finite() or discount_percent_decimal < 0 or discount_percent_decimal > 100:
        return {"success": False, "error": "Discount must be between 0 and 100 percent"}
    discount_amount_decimal = _money(subtotal_decimal * discount_percent_decimal / Decimal("100"))
    total_decimal = _money(subtotal_decimal - discount_amount_decimal)
    if payment_type == "Debit" and total_decimal <= 0:
        return {"success": False, "error": "Pay Later total must be greater than zero after discount"}

    subtotal = float(subtotal_decimal)
    discount_percent = float(discount_percent_decimal)
    discount_amount = float(discount_amount_decimal)
    total = float(total_decimal)
    paid = 0.0 if payment_type == "Debit" else total
    bill_no = storage.add_bill(
        customer_name, phone, items, total, paid, payment_type,
        subtotal=subtotal, discount_percent=discount_percent,
        discount_amount=discount_amount,
    )

    print_requested = _as_bool(data.get("print_receipt"), payment_type != "Debit")
    printed = False
    if print_requested and printer is not None:
        try:
            setting = lambda key, fallback: storage.get_setting(key) or fallback
            printed = bool(printer.print_bill(
                shop_name=setting("shop_name", Config.SHOP_NAME),
                shop_address=setting("shop_address", Config.SHOP_ADDRESS),
                shop_contact=setting("shop_contact", Config.SHOP_CONTACT), bill_no=bill_no,
                customer_name=customer_name, phone=phone, items=items,
                subtotal=subtotal, discount_percent=discount_percent,
                discount_amount=discount_amount, total=total,
                paid=paid, payment_type=payment_type,
                footer=setting("bill_footer", Config.BILL_FOOTER),
            ))
        except Exception as e:
            logger.warning(f"Print failed for bill #{bill_no}: {e}")
            printed = False

    if hasattr(storage, "mark_bill_print_status"):
        try:
            storage.mark_bill_print_status(bill_no, print_requested, printed)
        except Exception as e:
            logger.warning(f"Could not save print status for bill #{bill_no}: {e}")

    result = {
        "success": True, "bill_no": bill_no, "subtotal": subtotal,
        "discount_percent": discount_percent, "discount_amount": discount_amount, "total": total,
        "paid": paid, "payment_type": payment_type,
        "print_requested": print_requested, "printed": printed,
    }
    if payment_type == "Debit" and hasattr(storage, "get_recent_bills"):
        bill = next((b for b in storage.get_recent_bills(50) if str(b.get("bill_no")) == str(bill_no)), None)
        if bill:
            result["account_id"] = bill.get("account_id", "")
            if result["account_id"] and hasattr(storage, "get_debit_account"):
                result["balance"] = storage.get_debit_account(result["account_id"])["balance"]
    return result


def print_debit_payment_receipt(storage, printer, payment: dict) -> bool:
    """Print and persist the outcome for a received debit payment."""
    printed = False
    if printer is not None:
        try:
            setting = lambda key, fallback: storage.get_setting(key) or fallback
            printed = bool(printer.print_debit_payment(
                shop_name=setting("shop_name", Config.SHOP_NAME),
                shop_address=setting("shop_address", Config.SHOP_ADDRESS),
                shop_contact=setting("shop_contact", Config.SHOP_CONTACT),
                customer_name=payment["customer_name"], phone=payment["phone"],
                payment_id=payment["payment_id"], amount=payment["amount"],
                payment_method=payment["payment_method"],
                previous_balance=payment["balance"] + payment["amount"],
                balance=payment["balance"], note=payment["note"],
                footer=setting("bill_footer", Config.BILL_FOOTER),
            ))
        except Exception as e:
            logger.warning(f"Debit payment receipt failed: {e}")
    if hasattr(storage, "mark_debit_payment_print_status"):
        try:
            storage.mark_debit_payment_print_status(payment["payment_id"], printed)
        except Exception as e:
            logger.warning(f"Could not save debit payment print status: {e}")
    payment["print_requested"] = True
    payment["printed"] = printed
    return printed
