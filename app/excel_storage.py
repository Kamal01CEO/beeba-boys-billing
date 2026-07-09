"""
Billing Software — Excel ledger backend.
JSON stays the source of truth; bills.xlsx is a derived export rewritten on every change.
"""
import os
import logging

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from app import local_storage as ls
from app.local_storage import LocalStorage

logger = logging.getLogger("billing")

HEADER = ["Timestamp", "Bill No", "Customer", "Phone", "Items",
          "Total", "Paid", "Change", "Payment Type", "Status", "Deleted At"]


class ExcelStorage(LocalStorage):
    """LocalStorage + an Excel mirror at data/bills.xlsx."""

    def __init__(self, xlsx_path: str | None = None):
        self.xlsx_path = xlsx_path or os.path.join(ls.DATA_DIR, "bills.xlsx")

    # --- mutators: write JSON (super) then sync Excel ---
    def add_bill(self, *args, **kwargs):
        result = super().add_bill(*args, **kwargs)
        self._sync_excel()
        return result

    def edit_bill(self, *args, **kwargs):
        result = super().edit_bill(*args, **kwargs)
        self._sync_excel()
        return result

    def delete_bill(self, *args, **kwargs):
        result = super().delete_bill(*args, **kwargs)
        self._sync_excel()
        return result

    def set_setting(self, *args, **kwargs):
        result = super().set_setting(*args, **kwargs)
        self._sync_excel()
        return result

    def _sync_excel(self):
        try:
            bills = ls._load_json(ls.BILLS_PATH, [])
            wb = Workbook()
            ws = wb.active
            ws.title = "Bills"
            ws.append(HEADER)
            for cell in ws[1]:
                cell.font = Font(bold=True)
            ws.freeze_panes = "A2"

            del_fill = PatternFill("solid", fgColor="FFF0F0")
            for b in bills:
                ws.append([
                    b.get("timestamp", ""), b.get("bill_no", ""), b.get("customer_name", ""),
                    b.get("phone", ""), b.get("items", ""), b.get("total", 0), b.get("paid", 0),
                    b.get("change", 0), b.get("payment_type", ""), b.get("status", "active"),
                    b.get("deleted_at", ""),
                ])
                if b.get("status") == "deleted":
                    for cell in ws[ws.max_row]:
                        cell.fill = del_fill
            for row in ws.iter_rows(min_row=2, min_col=6, max_col=8):
                for cell in row:
                    cell.number_format = u"₹#,##0"

            summary = wb.create_sheet("Summary")
            summary.append(["Date", "Cash", "UPI", "Total", "Bill Count"])
            for cell in summary[1]:
                cell.font = Font(bold=True)
            days: dict[str, dict] = {}
            for b in bills:
                if b.get("status") == "deleted":
                    continue
                day = str(b.get("timestamp", ""))[:10]
                if not day:
                    continue
                agg = days.setdefault(day, {"Cash": 0.0, "UPI": 0.0, "total": 0.0, "count": 0})
                amount = float(b.get("total", 0) or 0)
                agg["total"] += amount
                agg["count"] += 1
                ptype = b.get("payment_type", "Cash")
                if ptype in ("Cash", "UPI"):
                    agg[ptype] += amount
            for day in sorted(days):
                a = days[day]
                summary.append([day, a["Cash"], a["UPI"], a["total"], a["count"]])

            tmp = self.xlsx_path + ".tmp"
            wb.save(tmp)
            os.replace(tmp, self.xlsx_path)
        except (PermissionError, OSError) as e:
            logger.warning(f"Excel sync skipped (file open/locked?): {e}")
