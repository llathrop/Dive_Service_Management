"""PDF generation utilities for invoices and price lists.

Uses fpdf2 to generate professional PDF documents without requiring
system-level dependencies like WeasyPrint or wkhtmltopdf.
"""

import os

from flask import current_app
from fpdf import FPDF

from app.services import config_service


# ---------------------------------------------------------------------------
# Colour / style constants
# ---------------------------------------------------------------------------

_HEADER_BG = (41, 65, 94)       # Dark blue
_HEADER_FG = (255, 255, 255)    # White
_ROW_ALT_BG = (240, 245, 250)   # Light blue-grey
_LINE_COLOR = (200, 200, 200)   # Light grey for rules
_ACCENT = (41, 65, 94)          # Same dark blue for headings


def _fmt_currency(value):
    """Format a numeric value as a dollar amount string."""
    if value is None:
        return "$0.00"
    return f"${float(value):,.2f}"


def _safe_str(value, default=""):
    """Return str(value) or *default* when value is None/empty."""
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


# =========================================================================
# Company header helper (shared between invoice and price list PDFs)
# =========================================================================

def _resolve_logo_path(config_key):
    """Return the absolute filesystem path for a logo config key, or None."""
    rel_path = _safe_str(config_service.get_config(config_key), "")
    if not rel_path or ".." in rel_path or rel_path.startswith("/"):
        return None
    try:
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    except RuntimeError:
        return None
    abs_path = os.path.join(upload_folder, rel_path)
    if os.path.isfile(abs_path):
        return abs_path
    return None


def _draw_company_header(pdf):
    """Draw the company header block at the top of the page.

    Reads company details from config_service and renders a left-aligned
    block with the company name, address, phone, and email.  If a logo
    is configured, it is displayed to the left of the company name.

    Logo resolution: ``company.invoice_logo_path`` first, then
    ``company.logo_path`` as fallback.

    Returns the Y position after the header.
    """
    company_name = _safe_str(config_service.get_config("company.name"), "Dive Service Management")
    company_address = _safe_str(config_service.get_config("company.address"), "")
    company_phone = _safe_str(config_service.get_config("company.phone"), "")
    company_email = _safe_str(config_service.get_config("company.email"), "")

    # Try to resolve a logo image
    logo_path = _resolve_logo_path("company.invoice_logo_path")
    if logo_path is None:
        logo_path = _resolve_logo_path("company.logo_path")

    text_x = pdf.l_margin
    if logo_path:
        try:
            logo_h = 15  # mm
            pdf.image(logo_path, x=pdf.l_margin, y=pdf.get_y(), h=logo_h)
            text_x = pdf.l_margin + 20  # offset text to the right of the logo
        except Exception:
            # If image fails for any reason, fall back to text-only
            pass

    # Company name
    pdf.set_x(text_x)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(0, 10, company_name, new_x="LMARGIN", new_y="NEXT")

    # Contact details
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    contact_parts = [p for p in (company_address, company_phone, company_email) if p]
    if contact_parts:
        pdf.cell(0, 5, "  |  ".join(contact_parts), new_x="LMARGIN", new_y="NEXT")

    # Horizontal rule
    pdf.ln(3)
    pdf.set_draw_color(*_LINE_COLOR)
    pdf.set_line_width(0.5)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(5)

    return pdf.get_y()


# =========================================================================
# Invoice PDF
# =========================================================================

def generate_invoice_pdf(invoice):
    """Generate a professional PDF for the given Invoice object.

    Args:
        invoice: An Invoice model instance with customer, line_items,
                 and payments relationships loaded.

    Returns:
        bytes -- The raw PDF content.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    # --- Company header ---
    _draw_company_header(pdf)

    # --- Invoice title and info ---
    _draw_invoice_info(pdf, invoice)

    # --- Customer info ---
    _draw_customer_info(pdf, invoice)

    # --- Line items table ---
    _draw_line_items_table(pdf, invoice)

    # --- Totals ---
    _draw_totals(pdf, invoice)

    # --- Payment history ---
    _draw_payments(pdf, invoice)

    # --- Footer ---
    _draw_invoice_footer(pdf, invoice)

    return pdf.output()


def _draw_invoice_info(pdf, invoice):
    """Draw the invoice number, dates, and status block."""
    y_start = pdf.get_y()

    # Left side: INVOICE title
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(95, 12, "INVOICE", new_x="RIGHT", new_y="TOP")

    # Right side: invoice details
    x_right = pdf.get_x()
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)

    details = [
        ("Invoice #:", _safe_str(invoice.invoice_number)),
        ("Status:", _safe_str(invoice.display_status, "Draft")),
        ("Issue Date:", invoice.issue_date.strftime("%m/%d/%Y") if invoice.issue_date else "N/A"),
        ("Due Date:", invoice.due_date.strftime("%m/%d/%Y") if invoice.due_date else "N/A"),
    ]

    for label, value in details:
        pdf.set_x(x_right)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(30, 6, label, new_x="RIGHT", new_y="TOP")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(55, 6, value, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)


def _draw_customer_info(pdf, invoice):
    """Draw the Bill To customer block."""
    customer = invoice.customer

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(0, 7, "BILL TO", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(40, 40, 40)

    # Customer name
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, _safe_str(customer.display_name), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)

    # Address
    if customer.address_line1:
        pdf.cell(0, 5, customer.address_line1, new_x="LMARGIN", new_y="NEXT")
    if customer.address_line2:
        pdf.cell(0, 5, customer.address_line2, new_x="LMARGIN", new_y="NEXT")

    city_state_parts = []
    if customer.city:
        city_state_parts.append(customer.city)
    if customer.state_province:
        if city_state_parts:
            city_state_parts[-1] += ","
        city_state_parts.append(customer.state_province)
    if customer.postal_code:
        city_state_parts.append(customer.postal_code)
    city_line = " ".join(city_state_parts)
    if city_line:
        pdf.cell(0, 5, city_line, new_x="LMARGIN", new_y="NEXT")

    # Phone/email
    if customer.phone_primary:
        pdf.cell(0, 5, f"Phone: {customer.phone_primary}", new_x="LMARGIN", new_y="NEXT")
    if customer.email:
        pdf.cell(0, 5, f"Email: {customer.email}", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)


def _draw_line_items_table(pdf, invoice):
    """Draw the line items table with header, rows, and alternating colours."""
    # Resolve line items (dynamic relationship returns query, not list)
    items = invoice.line_items.all() if hasattr(invoice.line_items, "all") else list(invoice.line_items)

    # Column widths (total = 180 for 15mm margins on A4)
    col_w = {
        "desc": 90,
        "qty": 20,
        "unit": 35,
        "total": 35,
    }

    # Table header
    pdf.set_fill_color(*_HEADER_BG)
    pdf.set_text_color(*_HEADER_FG)
    pdf.set_font("Helvetica", "B", 9)

    pdf.cell(col_w["desc"], 8, "  Description", fill=True, new_x="RIGHT", new_y="TOP")
    pdf.cell(col_w["qty"], 8, "Qty", fill=True, align="C", new_x="RIGHT", new_y="TOP")
    pdf.cell(col_w["unit"], 8, "Unit Price", fill=True, align="R", new_x="RIGHT", new_y="TOP")
    pdf.cell(col_w["total"], 8, "Line Total", fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    # Table rows
    pdf.set_text_color(40, 40, 40)

    if not items:
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(sum(col_w.values()), 8, "  No line items", new_x="LMARGIN", new_y="NEXT")
    else:
        for i, item in enumerate(items):
            # Alternating row background
            if i % 2 == 1:
                pdf.set_fill_color(*_ROW_ALT_BG)
                fill = True
            else:
                fill = False

            pdf.set_font("Helvetica", "", 9)

            desc = _safe_str(item.description)
            qty = _safe_str(item.quantity, "1")
            unit = _fmt_currency(item.unit_price)
            total = _fmt_currency(item.line_total)

            # Check if description needs wrapping
            desc_width = pdf.get_string_width(desc)
            if desc_width > col_w["desc"] - 4:
                # Multi-line row: use multi_cell for description
                y_before = pdf.get_y()
                x_start = pdf.get_x()

                # Draw fill for the whole row if needed
                if fill:
                    row_h = _calc_multi_line_height(pdf, desc, col_w["desc"] - 4)
                    pdf.rect(x_start, y_before, sum(col_w.values()), row_h, "F")

                # Description (multi_cell)
                pdf.set_xy(x_start, y_before)
                pdf.multi_cell(col_w["desc"], 5, f"  {desc}", new_x="RIGHT", new_y="TOP")
                y_after_desc = pdf.get_y()

                # Qty, unit price, total on first line
                pdf.set_xy(x_start + col_w["desc"], y_before)
                pdf.cell(col_w["qty"], 5, qty, align="C", new_x="RIGHT", new_y="TOP")
                pdf.cell(col_w["unit"], 5, unit, align="R", new_x="RIGHT", new_y="TOP")
                pdf.cell(col_w["total"], 5, total, align="R", new_x="LMARGIN", new_y="NEXT")

                # Move Y to the bottom of the description if it was taller
                pdf.set_y(max(y_after_desc, pdf.get_y()))
            else:
                pdf.cell(col_w["desc"], 7, f"  {desc}", fill=fill, new_x="RIGHT", new_y="TOP")
                pdf.cell(col_w["qty"], 7, qty, fill=fill, align="C", new_x="RIGHT", new_y="TOP")
                pdf.cell(col_w["unit"], 7, unit, fill=fill, align="R", new_x="RIGHT", new_y="TOP")
                pdf.cell(col_w["total"], 7, total, fill=fill, align="R", new_x="LMARGIN", new_y="NEXT")

    # Bottom rule
    pdf.set_draw_color(*_LINE_COLOR)
    pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(3)


def _calc_multi_line_height(pdf, text, max_width):
    """Estimate multi-line cell height for a given text and width."""
    words = text.split()
    lines = 1
    current_width = 0
    for word in words:
        word_width = pdf.get_string_width(word + " ")
        if current_width + word_width > max_width:
            lines += 1
            current_width = word_width
        else:
            current_width += word_width
    return lines * 5


def _draw_totals(pdf, invoice):
    """Draw the financial totals section on the right side."""
    # Right-align the totals block
    x_label = pdf.w - pdf.r_margin - 70
    x_value = pdf.w - pdf.r_margin - 35
    col_label = 35
    col_value = 35

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)

    rows = [
        ("Subtotal:", _fmt_currency(invoice.subtotal), False),
    ]

    # Tax (only if non-zero)
    tax_rate = float(invoice.tax_rate) if invoice.tax_rate else 0
    tax_amount = float(invoice.tax_amount) if invoice.tax_amount else 0
    if tax_amount > 0:
        tax_label = f"Tax ({tax_rate * 100:.2f}%):"
        rows.append((tax_label, _fmt_currency(invoice.tax_amount), False))

    # Discount (only if non-zero)
    discount = float(invoice.discount_amount) if invoice.discount_amount else 0
    if discount > 0:
        rows.append(("Discount:", f"-{_fmt_currency(invoice.discount_amount)}", False))

    rows.append(("Total:", _fmt_currency(invoice.total), True))
    rows.append(("Amount Paid:", _fmt_currency(invoice.amount_paid), False))
    rows.append(("Balance Due:", _fmt_currency(invoice.balance_due), True))

    for label, value, bold in rows:
        pdf.set_x(x_label)
        if bold:
            pdf.set_font("Helvetica", "B", 10)
        else:
            pdf.set_font("Helvetica", "", 10)
        pdf.cell(col_label, 7, label, align="R", new_x="RIGHT", new_y="TOP")
        pdf.cell(col_value, 7, value, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)


def _draw_payments(pdf, invoice):
    """Draw the payment history section if any payments exist."""
    payments = invoice.payments.all() if hasattr(invoice.payments, "all") else list(invoice.payments)

    if not payments:
        return

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(0, 8, "Payment History", new_x="LMARGIN", new_y="NEXT")

    # Payment table header
    col_w = {"date": 35, "method": 40, "type": 30, "amount": 35, "ref": 40}

    pdf.set_fill_color(*_HEADER_BG)
    pdf.set_text_color(*_HEADER_FG)
    pdf.set_font("Helvetica", "B", 8)

    pdf.cell(col_w["date"], 7, "  Date", fill=True, new_x="RIGHT", new_y="TOP")
    pdf.cell(col_w["method"], 7, "Method", fill=True, new_x="RIGHT", new_y="TOP")
    pdf.cell(col_w["type"], 7, "Type", fill=True, new_x="RIGHT", new_y="TOP")
    pdf.cell(col_w["amount"], 7, "Amount", fill=True, align="R", new_x="RIGHT", new_y="TOP")
    pdf.cell(col_w["ref"], 7, "Reference", fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(40, 40, 40)
    pdf.set_font("Helvetica", "", 8)

    for i, payment in enumerate(payments):
        if i % 2 == 1:
            pdf.set_fill_color(*_ROW_ALT_BG)
            fill = True
        else:
            fill = False

        date_str = payment.payment_date.strftime("%m/%d/%Y") if payment.payment_date else ""
        method = _safe_str(payment.payment_method, "").replace("_", " ").title()
        ptype = _safe_str(payment.payment_type, "").title()
        amount = _fmt_currency(payment.amount)
        ref = _safe_str(payment.reference_number, "")

        pdf.cell(col_w["date"], 6, f"  {date_str}", fill=fill, new_x="RIGHT", new_y="TOP")
        pdf.cell(col_w["method"], 6, method, fill=fill, new_x="RIGHT", new_y="TOP")
        pdf.cell(col_w["type"], 6, ptype, fill=fill, new_x="RIGHT", new_y="TOP")
        pdf.cell(col_w["amount"], 6, amount, fill=fill, align="R", new_x="RIGHT", new_y="TOP")
        pdf.cell(col_w["ref"], 6, ref, fill=fill, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)


def _draw_invoice_footer(pdf, invoice):
    """Draw the invoice footer with terms and thank-you note."""
    # Terms
    terms = _safe_str(invoice.terms) if invoice.terms else _safe_str(
        config_service.get_config("invoice.default_terms"), ""
    )

    if terms:
        pdf.set_draw_color(*_LINE_COLOR)
        pdf.set_line_width(0.3)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*_ACCENT)
        pdf.cell(0, 6, "Payment Terms", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 5, terms, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # Thank you
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, "Thank you for your business!", align="C", new_x="LMARGIN", new_y="NEXT")


# =========================================================================
# Price List PDF
# =========================================================================

def generate_price_list_pdf(categories_with_items):
    """Generate a customer-facing price list PDF.

    Args:
        categories_with_items: A dict mapping PriceListCategory instances
            to lists of PriceListItem instances, already sorted.

    Returns:
        bytes -- The raw PDF content.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    # --- Company header ---
    _draw_company_header(pdf)

    # --- Price List title ---
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(0, 12, "SERVICE PRICE LIST", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Column widths
    col_w = {"name": 70, "desc": 75, "price": 35}

    for category, items in categories_with_items.items():
        # Category header
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*_ACCENT)
        pdf.set_fill_color(*_HEADER_BG)
        pdf.set_text_color(*_HEADER_FG)
        pdf.cell(0, 8, f"  {category.name}", fill=True, new_x="LMARGIN", new_y="NEXT")

        if category.description:
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 5, f"  {category.description}", new_x="LMARGIN", new_y="NEXT")

        # Items
        pdf.set_text_color(40, 40, 40)
        for i, item in enumerate(items):
            if i % 2 == 1:
                pdf.set_fill_color(*_ROW_ALT_BG)
                fill = True
            else:
                fill = False

            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(col_w["name"], 6, f"  {item.name}", fill=fill, new_x="RIGHT", new_y="TOP")

            pdf.set_font("Helvetica", "", 8)
            desc = _safe_str(item.description, "")
            # Truncate long descriptions to fit
            max_desc_w = col_w["desc"] - 2
            if pdf.get_string_width(desc) > max_desc_w:
                while pdf.get_string_width(desc + "...") > max_desc_w and len(desc) > 0:
                    desc = desc[:-1]
                desc = desc.rstrip() + "..."

            pdf.cell(col_w["desc"], 6, desc, fill=fill, new_x="RIGHT", new_y="TOP")

            pdf.set_font("Helvetica", "B", 9)
            price_str = _fmt_currency(item.price)
            if item.is_per_unit and item.unit_label and item.unit_label != "each":
                price_str += f"/{item.unit_label}"
            pdf.cell(col_w["price"], 6, price_str, fill=fill, align="R", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(4)

    # Footer
    pdf.set_draw_color(*_LINE_COLOR)
    pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(5)

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, "Prices subject to change without notice.", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, "Thank you for your business!", align="C", new_x="LMARGIN", new_y="NEXT")

    return pdf.output()
