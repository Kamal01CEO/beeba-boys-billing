"""
Billing Software — REST API Routes (for agent integration)
"""
from flask import Blueprint, request, jsonify
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

        from app.billing_service import create_and_print
        from app.printer import PrinterManager
        storage = get_sheets()
        result = create_and_print(storage, PrinterManager.from_config_and_settings(storage), {
            "customer_name": customer_name, "phone": phone,
            "items": items, "payment_type": payment_type,
            "discount_percent": data.get("discount_percent", 0),
            "print_receipt": data.get("print_receipt"),
        })
        if not result["success"]:
            return jsonify(result), 400
        result["shop"] = storage.get_setting("shop_name") or Config.SHOP_NAME
        result["outstanding_debit"] = storage.get_total_outstanding() if hasattr(storage, "get_total_outstanding") else 0
        return jsonify(result)

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
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
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
    """Get earnings for today, 7d, 30d, or 1y."""
    try:
        sheets = get_sheets()
        from app.analytics import period_stats
        stats = period_stats(sheets, request.args.get("range", "today"))
        recent = sheets.get_recent_bills(10)
        active_bills = [b for b in recent if b.get("status") != "deleted"]
        deleted_bills = [b for b in recent if b.get("status") == "deleted"]
        return jsonify({
            "success": True,
            "total": stats["total"],
            "cash": stats["cash"],
            "upi": stats["upi"],
            "bills": stats["bills"],
            "customers": stats["customers"],
            "period": stats["period"],
            "period_label": stats["period_label"],
            "recent": active_bills,
            "deleted_bills": deleted_bills,
            "shop": Config.SHOP_NAME,
            "outstanding_debit": sheets.get_total_outstanding() if hasattr(sheets, "get_total_outstanding") else 0,
        })
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
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


@api_bp.route("/debits")
def list_debit_accounts_api():
    try:
        storage = get_sheets()
        return jsonify({
            "success": True,
            "accounts": storage.get_debit_accounts(),
            "total_outstanding": storage.get_total_outstanding(),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/debits/<account_id>")
def get_debit_account_api(account_id: str):
    try:
        return jsonify({"success": True, "account": get_sheets().get_debit_account(account_id)})
    except KeyError as e:
        return jsonify({"success": False, "error": str(e).strip("'")}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/debits/<account_id>/payments", methods=["POST"])
def receive_debit_payment_api(account_id: str):
    try:
        data = request.get_json(silent=True) or {}
        storage = get_sheets()
        payment = storage.record_debit_payment(
            account_id, data.get("amount"), data.get("payment_method", "Cash"), data.get("note", "")
        )
        from app.billing_service import print_debit_payment_receipt
        from app.printer import PrinterManager
        print_debit_payment_receipt(storage, PrinterManager.from_config_and_settings(storage), payment)
        return jsonify({"success": True, "payment": payment})
    except KeyError as e:
        return jsonify({"success": False, "error": str(e).strip("'")}), 404
    except (TypeError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


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
