"""
Billing Software — Dashboard Web UI Routes
"""
from flask import Blueprint, render_template, request, jsonify
from app.printer import PrinterManager
from app.config import Config
import os

from app.storage import get_storage

dashboard_bp = Blueprint("dashboard", __name__)

def get_sheets():
    return get_storage()


def get_printer():
    return PrinterManager.from_config_and_settings(get_storage())


@dashboard_bp.route("/")
def index():
    """Main billing dashboard."""
    storage = get_sheets()
    return render_template(
        "index.html",
        shop_name=storage.get_setting("shop_name") or Config.SHOP_NAME,
        shop_contact=storage.get_setting("shop_contact") or Config.SHOP_CONTACT,
    )


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
            "discount_percent": request.form.get("discount_percent", 0),
            "print_receipt": request.form.get("print_receipt"),
        })
        if not result["success"]:
            return jsonify(result), 400
        response = {
            "success": True,
            "bill_no": result["bill_no"],
            "subtotal": result["subtotal"],
            "discount_percent": result["discount_percent"],
            "discount_amount": result["discount_amount"],
            "total": result["total"],
            "paid": result["paid"],
            "payment_type": result["payment_type"],
            "printed": result["printed"],
            "print_requested": result["print_requested"],
            "message": f"Bill #{result['bill_no']} generated successfully!",
        }
        if result.get("account_id"):
            response["account_id"] = result["account_id"]
            response["balance"] = result["balance"]
        return jsonify(response)

    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/earnings")
def earnings():
    """Get the selected reporting-period summary for dashboard."""
    try:
        sheets = get_sheets()
        from app.analytics import period_stats
        stats = period_stats(sheets, request.args.get("range", "today"))
        recent = sheets.get_recent_bills(10)
        # Split into active and deleted
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
            "outstanding_debit": sheets.get_total_outstanding() if hasattr(sheets, "get_total_outstanding") else 0,
        })
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── Customer debit ledger ───
@dashboard_bp.route("/debits")
def debit_accounts():
    try:
        storage = get_sheets()
        accounts = storage.get_debit_accounts()
        return jsonify({
            "success": True,
            "accounts": accounts,
            "total_outstanding": storage.get_total_outstanding(),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/debits/<account_id>")
def debit_account(account_id: str):
    try:
        return jsonify({"success": True, "account": get_sheets().get_debit_account(account_id)})
    except KeyError as e:
        return jsonify({"success": False, "error": str(e).strip("'")}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def _request_payload():
    return request.get_json(silent=True) or request.form.to_dict()


@dashboard_bp.route("/debits/<account_id>/purchase", methods=["POST"])
def add_debit_purchase(account_id: str):
    try:
        storage = get_sheets()
        account = storage.get_debit_account(account_id)
        data = _request_payload()
        items = data.get("items", [])
        if isinstance(items, str):
            import json
            items = json.loads(items)
        from app.billing_service import create_and_print
        result = create_and_print(storage, get_printer(), {
            "customer_name": account["customer_name"],
            "phone": account["phone"],
            "items": items,
            "payment_type": "Debit",
            "discount_percent": data.get("discount_percent", 0),
            "print_receipt": data.get("print_receipt"),
        })
        if not result["success"]:
            return jsonify(result), 400
        return jsonify(result)
    except KeyError as e:
        return jsonify({"success": False, "error": str(e).strip("'")}), 404
    except (TypeError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/debits/<account_id>/payments", methods=["POST"])
def receive_debit_payment(account_id: str):
    try:
        data = _request_payload()
        storage = get_sheets()
        payment = storage.record_debit_payment(
            account_id=account_id,
            amount=data.get("amount"),
            payment_method=data.get("payment_method", "Cash"),
            note=data.get("note", ""),
        )
        from app.billing_service import print_debit_payment_receipt
        print_debit_payment_receipt(storage, get_printer(), payment)
        return jsonify({"success": True, "payment": payment})
    except KeyError as e:
        return jsonify({"success": False, "error": str(e).strip("'")}), 404
    except (TypeError, ValueError) as e:
        return jsonify({"success": False, "error": str(e)}), 400
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
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
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


@dashboard_bp.route("/backup", methods=["POST"])
def create_backup():
    try:
        path = get_sheets().create_backup("manual")
        return jsonify({"success": True, "path": path})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/system-info")
def system_info():
    from app import local_storage as ls
    return jsonify({"success": True, "data_dir": ls.DATA_DIR, "backup_dir": ls.BACKUP_DIR})


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
