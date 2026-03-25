"""Customer-portal invoice read models and safe view helpers."""

from decimal import Decimal

from app.extensions import db
from app.models.invoice import Invoice, InvoiceLineItem
from app.services import audit_service, payment_provider_service

PORTAL_VISIBLE_INVOICE_STATUSES = (
    "sent",
    "viewed",
    "partially_paid",
    "paid",
    "overdue",
    "void",
    "refunded",
)


def get_customer_invoices(customer_id, page=1, per_page=10):
    """Return a paginated invoice list for a specific customer."""
    query = (
        Invoice.query.filter(Invoice.customer_id == customer_id)
        .filter(Invoice.status.in_(PORTAL_VISIBLE_INVOICE_STATUSES))
        .order_by(Invoice.issue_date.desc(), Invoice.id.desc())
    )
    return db.paginate(query, page=page, per_page=per_page)


def get_customer_recent_invoices(customer_id, limit=5):
    """Return the most recent invoices for a customer."""
    return (
        Invoice.query.filter(Invoice.customer_id == customer_id)
        .filter(Invoice.status.in_(PORTAL_VISIBLE_INVOICE_STATUSES))
        .order_by(Invoice.issue_date.desc(), Invoice.id.desc())
        .limit(limit)
        .all()
    )


def get_customer_invoice(customer_id, invoice_id):
    """Return a customer-owned invoice or None if it does not belong to them."""
    return (
        Invoice.query.filter(Invoice.customer_id == customer_id)
        .filter(Invoice.id == invoice_id)
        .filter(Invoice.status.in_(PORTAL_VISIBLE_INVOICE_STATUSES))
        .first()
    )


def _safe_line_item_description(line_item):
    """Return a customer-safe line-item description."""
    if line_item.line_type == "labor":
        return "Labor"
    return line_item.description or ""


def serialize_invoice_line_item(line_item):
    """Serialize a line item into a portal-safe dict."""
    quantity = Decimal(str(line_item.quantity or 0))
    unit_price = Decimal(str(line_item.unit_price or 0))
    line_total = Decimal(str(line_item.line_total or 0))
    return {
        "id": line_item.id,
        "line_type": line_item.line_type,
        "description": _safe_line_item_description(line_item),
        "quantity": quantity,
        "unit_price": unit_price,
        "line_total": line_total,
        "sort_order": line_item.sort_order or 0,
    }


def get_customer_invoice_line_items(invoice):
    """Return safe line items for a customer-facing invoice view."""
    line_items = invoice.line_items.order_by(
        InvoiceLineItem.sort_order.asc(),
        InvoiceLineItem.id.asc(),
    ).all()
    return [serialize_invoice_line_item(item) for item in line_items]


def get_customer_invoice_status_history(customer_id, invoice_id):
    """Return the invoice status-change audit trail for the customer invoice."""
    invoice = get_customer_invoice(customer_id, invoice_id)
    if invoice is None:
        return None

    pagination = audit_service.get_audit_logs(
        entity_type="invoice",
        entity_id=invoice.id,
        action="status_change",
        page=1,
        per_page=100,
    )
    return list(reversed(pagination.items))


def get_customer_invoice_view(customer_id, invoice_id):
    """Build the portal-safe invoice view context for the given customer."""
    invoice = get_customer_invoice(customer_id, invoice_id)
    if invoice is None:
        return None

    line_items = get_customer_invoice_line_items(invoice)
    status_history = get_customer_invoice_status_history(customer_id, invoice_id) or []
    payment_context = payment_provider_service.build_invoice_context(invoice)

    return {
        "invoice": invoice,
        "line_items": line_items,
        "status_history": status_history,
        "payment_context": payment_context,
        "payments_summary": {
            "amount_paid": Decimal(str(invoice.amount_paid or 0)),
            "balance_due": Decimal(str(invoice.balance_due or 0)),
            "total": Decimal(str(invoice.total or 0)),
        },
    }


def get_portal_invoice_timeline_entry(entry):
    """Normalize audit log entries for template consumption."""
    return {
        "created_at": entry.created_at,
        "old_value": entry.old_value,
        "new_value": entry.new_value,
        "field_name": entry.field_name,
    }
