"""Billing Software — single create+print path shared by web, API, bot, MCP."""
import logging
from app.config import Config

logger = logging.getLogger("billing")


def create_and_print(storage, printer, data: dict) -> dict:
    customer_name = (data.get("customer_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    items = data.get("items") or []
    payment_type = data.get("payment_type") or "Cash"

    if not customer_name:
        return {"success": False, "error": "customer_name is required"}
    if not items:
        return {"success": False, "error": "At least one item is required"}

    total = sum(i["qty"] * i["price"] for i in items)
    bill_no = storage.add_bill(customer_name, phone, items, total, total, payment_type)

    printed = False
    if printer is not None:
        try:
            printed = bool(printer.print_bill(
                shop_name=Config.SHOP_NAME, shop_address=Config.SHOP_ADDRESS,
                shop_contact=Config.SHOP_CONTACT, bill_no=bill_no,
                customer_name=customer_name, phone=phone, items=items,
                total=total, paid=total, payment_type=payment_type, footer=Config.BILL_FOOTER,
            ))
        except Exception as e:
            logger.warning(f"Print failed for bill #{bill_no}: {e}")
            printed = False

    return {"success": True, "bill_no": bill_no, "total": total, "printed": printed}
