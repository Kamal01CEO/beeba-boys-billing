"""
Billing Software — REST API Routes (for agent integration)
"""
from flask import Blueprint, request, jsonify
from app.sheets import SheetsManager
from app.config import Config
import os

api_bp = Blueprint("api", __name__)
_sheets: SheetsManager = None


def get_sheets():
    global _sheets
    if _sheets is None:
        cred_path = Config.SERVICE_ACCOUNT_PATH
        if not os.path.exists(cred_path):
            raise FileNotFoundError(
                f"Service account file not found at {cred_path}"
            )
        _sheets = SheetsManager(Config.GOOGLE_SHEET_ID, cred_path)
    return _sheets


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


@api_bp.route("/earnings")
def get_earnings():
    """Get today's earnings."""
    try:
        sheets = get_sheets()
        total = sheets.get_today_earnings()
        by_payment = sheets.get_today_earnings_by_payment()
        return jsonify({
            "success": True,
            "total": total,
            "cash": by_payment.get("Cash", 0),
            "upi": by_payment.get("UPI", 0),
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
