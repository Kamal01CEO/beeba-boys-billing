"""
Billing Software — Dashboard Web UI Routes
"""
from flask import Blueprint, render_template, request, jsonify
from app.sheets import SheetsManager
from app.printer import PrinterManager
from app.config import Config
import os

from app.storage import get_storage

dashboard_bp = Blueprint("dashboard", __name__)

_printer: PrinterManager = None


def get_sheets():
    return get_storage()


def get_printer():
    return PrinterManager.from_config_and_settings(get_storage())


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

        from app.billing_service import create_and_print
        result = create_and_print(get_sheets(), get_printer(), {
            "customer_name": customer_name, "phone": phone,
            "items": items, "payment_type": payment_type,
        })
        if not result["success"]:
            return jsonify(result), 400
        return jsonify({
            "success": True,
            "bill_no": result["bill_no"],
            "total": result["total"],
            "printed": result["printed"],
            "message": f"Bill #{result['bill_no']} generated successfully!",
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
        recent = sheets.get_recent_bills(10)
        # Split into active and deleted
        active_bills = [b for b in recent if b.get("status") != "deleted"]
        deleted_bills = [b for b in recent if b.get("status") == "deleted"]
        from app.analytics import today_stats
        stats = today_stats(sheets)
        return jsonify({
            "success": True,
            "total": total,
            "cash": by_payment.get("Cash", 0),
            "upi": by_payment.get("UPI", 0),
            "bills": stats["bills"],
            "customers": stats["customers"],
            "recent": active_bills,
            "deleted_bills": deleted_bills,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/delete-bill/<int:bill_no>", methods=["POST"])
def delete_bill(bill_no: int):
    """Soft-delete a bill."""
    try:
        sheets = get_sheets()
        ok = sheets.delete_bill(bill_no)
        if ok:
            return jsonify({"success": True, "message": f"Bill #{bill_no} deleted"})
        return jsonify({"success": False, "error": "Bill not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/edit-bill/<int:bill_no>", methods=["POST"])
def edit_bill(bill_no: int):
    """Edit a bill."""
    try:
        customer_name = request.form.get("customer_name", "").strip()
        phone = request.form.get("phone", "").strip()
        payment_type = request.form.get("payment_type", "Cash")
        items_str = request.form.get("items", "").strip()

        updates = {}
        if customer_name:
            updates["customer_name"] = customer_name
        if phone:
            updates["phone"] = phone
        if payment_type:
            updates["payment_type"] = payment_type
        if items_str:
            updates["items"] = items_str

        sheets = get_sheets()
        ok = sheets.edit_bill(bill_no, **updates)
        if ok:
            return jsonify({"success": True, "message": f"Bill #{bill_no} updated"})
        return jsonify({"success": False, "error": "Bill not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Settings endpoints ───
@dashboard_bp.route("/settings", methods=["POST"])
def set_setting():
    """Save a setting key/value pair."""
    try:
        key = request.form.get("key", "").strip()
        value = request.form.get("value", "").strip()
        if not key:
            return jsonify({"success": False, "error": "Key is required"}), 400
        sheets = get_sheets()
        sheets.set_setting(key, value)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/settings/<key>")
def get_setting(key: str):
    """Get a setting value."""
    try:
        sheets = get_sheets()
        value = sheets.get_setting(key)
        return jsonify({"success": True, "value": value or ""})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/upload-logo", methods=["POST"])
def upload_logo():
    """Upload shop logo image."""
    try:
        if "logo" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400
        file = request.files["logo"]
        if file.filename == "":
            return jsonify({"success": False, "error": "No file selected"}), 400

        static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
        logo_path = os.path.join(static_dir, "logo.png")
        file.save(logo_path)

        # Convert to PNG if needed, resize
        try:
            from PIL import Image
            img = Image.open(logo_path)
            img.thumbnail((400, 500), Image.LANCZOS)
            img.save(logo_path, "PNG")
        except ImportError:
            pass  # Keep as-is if PIL not available

        return jsonify({"success": True, "message": "Logo updated"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
