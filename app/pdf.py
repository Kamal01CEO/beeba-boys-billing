"""
Billing Software — PDF Bill Generation (fallback when no printer)
"""
import io
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4, mm
from reportlab.pdfgen import canvas


def generate_bill_pdf(
    shop_name: str,
    shop_address: str,
    shop_contact: str,
    bill_no: int,
    customer_name: str,
    phone: str,
    items: list[dict],
    total: float,
    paid: float,
    payment_type: str,
    footer: str = "",
    subtotal: float | None = None,
    discount_percent: float = 0,
    discount_amount: float = 0,
) -> bytes:
    """
    Generate a bill PDF and return it as bytes.
    """
    buf = io.BytesIO()
    page_width = 80 * mm
    c = canvas.Canvas(buf, pagesize=(page_width, 297 * mm))
    width, _ = (page_width, 297 * mm)
    y = 275 * mm
    left_margin = 5 * mm

    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, y, shop_name)
    y -= 6 * mm

    c.setFont("Helvetica", 8)
    if shop_address:
        c.drawCentredString(width / 2, y, shop_address)
        y -= 4 * mm
    if shop_contact:
        c.drawCentredString(width / 2, y, f"Tel: {shop_contact}")
        y -= 4 * mm

    c.setFont("Helvetica", 8)
    c.line(left_margin, y, width - left_margin, y)
    y -= 4 * mm

    c.drawString(left_margin, y, f"Bill No: {bill_no}")
    c.drawRightString(width - left_margin, y, datetime.now().strftime("%d-%b-%Y %H:%M"))
    y -= 4 * mm
    c.drawString(left_margin, y, f"Customer: {customer_name}")
    y -= 4 * mm
    c.drawString(left_margin, y, f"Phone: {phone}")
    y -= 4 * mm

    c.line(left_margin, y, width - left_margin, y)
    y -= 4 * mm

    # Items header
    c.setFont("Helvetica-Bold", 9)
    c.drawString(left_margin, y, "Item")
    c.drawRightString(width * 0.6, y, "Qty")
    c.drawRightString(width - left_margin, y, "Amount")
    y -= 4 * mm
    c.setFont("Helvetica", 9)
    c.line(left_margin, y, width - left_margin, y)
    y -= 4 * mm

    for item in items:
        name = item["name"][:20]
        qty = item["qty"]
        price = item["price"]
        line_total = qty * price
        c.drawString(left_margin, y, name)
        c.drawRightString(width * 0.6, y, str(qty))
        c.drawRightString(width - left_margin, y, f"Rs {line_total:.0f}")
        y -= 4 * mm
        if y < 20 * mm:
            c.showPage()
            y = 275 * mm

    c.line(left_margin, y, width - left_margin, y)
    y -= 5 * mm

    subtotal = total if subtotal is None else subtotal
    if discount_amount > 0:
        c.setFont("Helvetica", 9)
        c.drawString(left_margin, y, f"Subtotal: Rs {subtotal:.2f}")
        y -= 4 * mm
        c.drawString(left_margin, y, f"Discount ({discount_percent:g}%): -Rs {discount_amount:.2f}")
        y -= 5 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, y, f"Total: Rs {total:.0f}")
    y -= 5 * mm
    c.setFont("Helvetica", 9)
    c.drawString(left_margin, y, f"Paid: Rs {paid:.0f} ({payment_type})")
    y -= 4 * mm

    change = paid - total
    if change >= 0:
        c.drawString(left_margin, y, f"Change: Rs {change:.0f}")
    else:
        c.drawString(left_margin, y, f"Due: Rs {abs(change):.0f}")
    y -= 5 * mm

    c.line(left_margin, y, width - left_margin, y)
    y -= 4 * mm

    if footer:
        c.setFont("Helvetica", 8)
        c.drawCentredString(width / 2, y, footer)

    c.save()
    buf.seek(0)
    return buf.getvalue()
