"""
Billing Software — REST API Routes (for agent integration)
"""
from flask import Blueprint, request, jsonify
from app.sheets import SheetsManager
from app.config import Config
import os

from app.storage import get_storage

api_bp = Blueprint("api", __name__)


def get_sheets():
    return get_storage()


@api_bp.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "shop": Config.SHOP_NAME})


@api_bp.route("/bill", methods=["POST"])
def create_bill():
    """
    Create a bill via API (for agent integration).

    POST JSON:
    {
        "customer_name": "Ramesh",
        "phone": "9876543210",
        "items": [{"name": "Shirt", "qty": 1, "price": 800}],
        "payment_type": "Cash"
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        customer_name = data.get("customer_name", "").strip()
        phone = data.get("phone", "").strip()
        items = data.get("items", [])
        payment_type = data.get("payment_type", "Cash")

        if not customer_name:
            return jsonify({"error": "customer_name is required"}), 400
        if not items:
            return jsonify({"error": "At least one item is required"}), 400

        total = sum(i["qty"] * i["price"] for i in items)
        sheets = get_sheets()
        bill_no = sheets.add_bill(customer_name, phone, items, total, total, payment_type)

        return jsonify({
            "success": True,
            "bill_no": bill_no,
            "total": total,
            "shop": Config.SHOP_NAME,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/bill/<int:bill_no>", methods=["DELETE"])
def delete_bill_api(bill_no: int):
    """Delete a bill by bill number."""
    try:
        sheets = get_sheets()
        ok = sheets.delete_bill(bill_no)
        if ok:
            return jsonify({"success": True, "message": f"Bill #{bill_no} deleted"})
        return jsonify({"success": False, "error": "Bill not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/bill/<int:bill_no>", methods=["PUT"])
def edit_bill_api(bill_no: int):
    """Edit a bill by bill number. Accepts JSON body with fields to update."""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        updates = {}
        for key in ("customer_name", "phone", "items", "total", "paid", "payment_type"):
            if key in data:
                updates[key] = data[key]

        if not updates:
            return jsonify({"error": "No valid fields to update"}), 400

        sheets = get_sheets()
        ok = sheets.edit_bill(bill_no, **updates)
        if ok:
            return jsonify({"success": True, "message": f"Bill #{bill_no} updated"})
        return jsonify({"success": False, "error": "Bill not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/earnings")
def get_earnings():
    """Get today's earnings."""
    try:
        sheets = get_sheets()
        total = sheets.get_today_earnings()
        by_payment = sheets.get_today_earnings_by_payment()
        recent = sheets.get_recent_bills(10)
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
            "shop": Config.SHOP_NAME,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/bills/recent")
def recent_bills():
    """Get recent bills."""
    try:
        sheets = get_sheets()
        limit = request.args.get("limit", 5, type=int)
        bills = sheets.get_recent_bills(limit)
        return jsonify({"success": True, "bills": bills})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/bills/search")
def search_bills():
    """Search bills by customer name or phone."""
    try:
        query = request.args.get("q", "").strip()
        if not query:
            return jsonify({"error": "query parameter 'q' is required"}), 400
        sheets = get_sheets()
        results = sheets.search_bills(query)
        return jsonify({"success": True, "results": results, "count": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Settings API ───
@api_bp.route("/settings", methods=["POST"])
def set_setting_api():
    """Save a setting key/value pair."""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "JSON body required"}), 400
        key = data.get("key", "").strip()
        value = data.get("value", "").strip()
        if not key:
            return jsonify({"error": "Key is required"}), 400
        sheets = get_sheets()
        sheets.set_setting(key, value)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/settings/<key>")
def get_setting_api(key: str):
    """Get a setting value."""
    try:
        sheets = get_sheets()
        value = sheets.get_setting(key)
        return jsonify({"success": True, "value": value or ""})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/upload-logo", methods=["POST"])
def upload_logo_api():
    """Upload shop logo image (multipart)."""
    try:
        if "logo" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400
        file = request.files["logo"]
        if file.filename == "":
            return jsonify({"success": False, "error": "No file selected"}), 400

        static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
        logo_path = os.path.join(static_dir, "logo.png")
        file.save(logo_path)

        try:
            from PIL import Image
            img = Image.open(logo_path)
            img.thumbnail((400, 500), Image.LANCZOS)
            img.save(logo_path, "PNG")
        except ImportError:
            pass

        return jsonify({"success": True, "message": "Logo updated"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
