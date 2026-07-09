"""
Billing Software — Dashboard Web UI Routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.sheets import SheetsManager
from app.printer import PrinterManager
from app.config import Config
import os

dashboard_bp = Blueprint("dashboard", __name__)

# Lazy init — created on first request
_sheets: SheetsManager = None
_printer: PrinterManager = None


def get_sheets():
    global _sheets
    if _sheets is None:
        cred_path = Config.SERVICE_ACCOUNT_PATH
        if not os.path.exists(cred_path):
            raise FileNotFoundError(
                f"Service account file not found at {cred_path}. "
                "See credentials/README.md for setup instructions."
            )
        _sheets = SheetsManager(Config.GOOGLE_SHEET_ID, cred_path)
    return _sheets


def get_printer():
    global _printer
    if _printer is None:
        _printer = PrinterManager(
            Config.PRINTER_VENDOR_ID, Config.PRINTER_PRODUCT_ID
        )
    return _printer


@dashboard_bp.route("/")
def index():
    """Main billing dashboard."""
    return render_template("index.html", shop_name=Config.SHOP_NAME)


@dashboard_bp.route("/generate-bill", methods=["POST"])
def generate_bill():
    """Generate a bill from dashboard form."""
    try:
        customer_name = request.form.get("customer_name", "").strip()
        phone = request.form.get("phone", "").strip()
        payment_type = request.form.get("payment_type", "Cash")

        if not customer_name:
            return jsonify({"success": False, "error": "Customer name is required"}), 400

        # Parse items from form
        items = []
        item_names = request.form.getlist("item_name[]")
        item_qtys = request.form.getlist("item_qty[]")
        item_prices = request.form.getlist("item_price[]")

        for name, qty_str, price_str in zip(item_names, item_qtys, item_prices):
            name = name.strip()
            if not name:
                continue
            try:
                qty = int(qty_str) if qty_str else 1
                price = float(price_str) if price_str else 0
            except ValueError:
                continue
            if qty > 0 and price > 0:
                items.append({"name": name, "qty": qty, "price": price})

        if not items:
            return jsonify({"success": False, "error": "At least one item is required"}), 400

        total = sum(i["qty"] * i["price"] for i in items)
        paid = total  # Full payment by default

        # Save to Google Sheets
        sheets = get_sheets()
        bill_no = sheets.add_bill(customer_name, phone, items, total, paid, payment_type)

        # Try to print
        printed = False
        printer = get_printer()
        if printer.connect():
            printed = printer.print_bill(
                shop_name=Config.SHOP_NAME,
                shop_address=Config.SHOP_ADDRESS,
                shop_contact=Config.SHOP_CONTACT,
                bill_no=bill_no,
                customer_name=customer_name,
                phone=phone,
                items=items,
                total=total,
                paid=paid,
                payment_type=payment_type,
                footer=Config.BILL_FOOTER,
            )
            printer.disconnect()

        return jsonify({
            "success": True,
            "bill_no": bill_no,
            "total": total,
            "printed": printed,
            "message": f"Bill #{bill_no} generated successfully!",
        })

    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/earnings")
def earnings():
    """Get today's earnings summary for dashboard."""
    try:
        sheets = get_sheets()
        total = sheets.get_today_earnings()
        by_payment = sheets.get_today_earnings_by_payment()
        recent = sheets.get_recent_bills(5)
        return jsonify({
            "success": True,
            "total": total,
            "cash": by_payment.get("Cash", 0),
            "upi": by_payment.get("UPI", 0),
            "recent": recent,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
