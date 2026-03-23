"""Invoice service layer — core business logic for billing workflow.

Provides module-level functions for managing invoices, invoice line items,
and payments.  Handles invoice generation from service orders, automatic
invoice numbering, totals recalculation, and payment tracking with
automatic status updates.

Invoices use status tracking (not soft-delete) since financial records
should be voided rather than deleted.
"""

import re
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.invoice import Invoice, InvoiceLineItem, invoice_orders
from app.models.payment import Payment
from app.models.service_order import ServiceOrder
from app.services import audit_service, notification_service


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SORTABLE_FIELDS = {
    "invoice_number",
    "status",
    "issue_date",
    "due_date",
    "total",
    "balance_due",
    "created_at",
}

INVOICE_NUMBER_PATTERN = re.compile(r"^INV-(\d{4})-(\d{5})$")

INVOICE_STATUS_TRANSITIONS = {
    "draft": {"sent", "void"},
    "sent": {"viewed", "partially_paid", "paid", "overdue", "void"},
    "viewed": {"partially_paid", "paid", "overdue", "void"},
    "partially_paid": {"paid", "overdue", "void"},
    "paid": {"refunded"},
    "overdue": {"partially_paid", "paid", "void"},
    "void": set(),
    "refunded": set(),
}


# =========================================================================
# Invoice CRUD
# =========================================================================

def get_invoices(
    page=1,
    per_page=25,
    search=None,
    status=None,
    date_from=None,
    date_to=None,
    overdue_only=False,
    sort="issue_date",
    order="desc",
):
    """Return paginated, filtered, sorted invoices.

    Args:
        page: Page number (1-indexed).
        per_page: Number of results per page.
        search: Optional search string (matches invoice_number, notes).
        status: Optional status filter.
        date_from: Optional start date for issue_date range.
        date_to: Optional end date for issue_date range.
        overdue_only: If True, only return overdue invoices.
        sort: Column name to sort by.  Must be in SORTABLE_FIELDS.
        order: Sort direction, 'asc' or 'desc'.

    Returns:
        A SQLAlchemy pagination object.
    """
    query = Invoice.query

    # Apply search filter
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Invoice.invoice_number.ilike(pattern),
                Invoice.notes.ilike(pattern),
            )
        )

    # Apply status filter
    if status:
        query = query.filter(Invoice.status == status)

    # Apply date range filters on issue_date
    if date_from is not None:
        query = query.filter(Invoice.issue_date >= date_from)
    if date_to is not None:
        query = query.filter(Invoice.issue_date <= date_to)

    # Apply overdue filter
    if overdue_only:
        query = query.filter(
            Invoice.due_date < date.today(),
            Invoice.status.notin_(["paid", "void", "refunded"]),
        )

    # Apply sorting (validate against allowlist)
    if sort not in SORTABLE_FIELDS:
        sort = "issue_date"
    sort_column = getattr(Invoice, sort, Invoice.issue_date)
    if order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    return db.paginate(query, page=page, per_page=per_page)


def get_invoice(invoice_id):
    """Return a single invoice by ID, or None if not found.

    Args:
        invoice_id: The primary key of the invoice.

    Returns:
        An Invoice instance, or None if not found.
    """
    return db.session.get(Invoice, invoice_id)


def create_invoice(data, created_by=None, ip_address=None, user_agent=None):
    """Create a new invoice from a data dict.

    Auto-generates the invoice_number using the INV-YYYY-NNNNN pattern.

    Args:
        data: Dictionary of invoice fields.
        created_by: Optional user ID of the creator.
        ip_address: Optional IP address for audit logging.
        user_agent: Optional user agent for audit logging.

    Returns:
        The newly created Invoice instance.
    """
    invoice = Invoice(
        customer_id=data["customer_id"],
        status=data.get("status", "draft"),
        issue_date=data.get("issue_date", date.today()),
        due_date=data.get("due_date"),
        tax_rate=data.get("tax_rate", Decimal("0.0000")),
        discount_amount=data.get("discount_amount", Decimal("0.00")),
        notes=data.get("notes"),
        customer_notes=data.get("customer_notes"),
        terms=data.get("terms"),
        created_by=created_by,
    )

    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            invoice.invoice_number = generate_invoice_number()
            db.session.add(invoice)
            db.session.flush()
            break
        except IntegrityError:
            db.session.rollback()
            if attempt == MAX_RETRIES - 1:
                raise

    db.session.commit()
    try:
        audit_service.log_action(
            action="create",
            entity_type="invoice",
            entity_id=invoice.id,
            user_id=created_by,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass
    return invoice


def update_invoice(invoice_id, data, user_id=None, ip_address=None, user_agent=None):
    """Update an existing invoice from a data dict.

    Args:
        invoice_id: The primary key of the invoice to update.
        data: Dictionary of fields to update.
        user_id: Optional user ID for audit logging.
        ip_address: Optional IP address for audit logging.
        user_agent: Optional user agent for audit logging.

    Returns:
        The updated Invoice instance, or None if not found.
    """
    invoice = get_invoice(invoice_id)
    if invoice is None:
        return None

    for field in (
        "customer_id",
        "issue_date",
        "due_date",
        "tax_rate",
        "discount_amount",
        "notes",
        "customer_notes",
        "terms",
    ):
        if field in data:
            setattr(invoice, field, data[field])

    # Recalculate totals if financial fields changed
    if "tax_rate" in data or "discount_amount" in data:
        invoice.recalculate_totals()

    db.session.commit()
    try:
        audit_service.log_action(
            action="update",
            entity_type="invoice",
            entity_id=invoice.id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass
    return invoice


def void_invoice(invoice_id, user_id=None, ip_address=None, user_agent=None):
    """Void an invoice by setting its status to 'void'.

    Args:
        invoice_id: The primary key of the invoice to void.
        user_id: Optional user ID for audit logging.
        ip_address: Optional IP address for audit logging.
        user_agent: Optional user agent for audit logging.

    Returns:
        The voided Invoice instance, or None if not found.
    """
    invoice = get_invoice(invoice_id)
    if invoice is None:
        return None

    old_status = invoice.status
    invoice.status = "void"
    db.session.commit()
    try:
        audit_service.log_action(
            action="status_change",
            entity_type="invoice",
            entity_id=invoice.id,
            user_id=user_id,
            field_name="status",
            old_value=old_status,
            new_value="void",
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass
    return invoice


def change_status(invoice_id, new_status, user_id=None, ip_address=None, user_agent=None):
    """Transition invoice to new status with validation.

    Only transitions allowed by INVOICE_STATUS_TRANSITIONS are permitted.
    When transitioning to 'paid', automatically sets the paid_date to today.

    Args:
        invoice_id: The primary key of the invoice.
        new_status: The desired new status string.
        user_id: Optional user ID for audit logging.
        ip_address: Optional IP address for audit logging.
        user_agent: Optional user agent for audit logging.

    Returns:
        A tuple of (invoice, success).  ``invoice`` is the Invoice instance
        (or None if not found); ``success`` is True when the transition
        was applied, False otherwise.
    """
    invoice = get_invoice(invoice_id)
    if invoice is None:
        return None, False
    if not new_status:
        return invoice, False
    allowed = INVOICE_STATUS_TRANSITIONS.get(invoice.status, set())
    if new_status not in allowed:
        return invoice, False
    old_status = invoice.status
    invoice.status = new_status
    if new_status == "paid":
        invoice.paid_date = date.today()
    db.session.commit()
    try:
        audit_service.log_action(
            action="status_change",
            entity_type="invoice",
            entity_id=invoice.id,
            user_id=user_id,
            field_name="status",
            old_value=old_status,
            new_value=new_status,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass
    return invoice, True


# =========================================================================
# Invoice Number Generation
# =========================================================================

def generate_invoice_number():
    """Generate the next sequential invoice number for the current year.

    Format: INV-{YEAR}-{SEQUENCE:05d}, e.g. "INV-2026-00001".

    Queries the maximum existing invoice_number for the current year,
    extracts the sequence portion, and increments it.  Falls back to
    a count-based approach if existing numbers don't match the expected
    pattern.

    Returns:
        A string like "INV-2026-00001".
    """
    current_year = date.today().year
    prefix = f"INV-{current_year}-"

    # Find the max invoice_number for the current year
    result = (
        db.session.query(Invoice.invoice_number)
        .filter(Invoice.invoice_number.like(f"{prefix}%"))
        .order_by(Invoice.invoice_number.desc())
        .first()
    )

    if result is not None:
        match = INVOICE_NUMBER_PATTERN.match(result[0])
        if match and int(match.group(1)) == current_year:
            next_seq = int(match.group(2)) + 1
        else:
            # Fallback: count existing invoices with this year's prefix
            count = (
                db.session.query(func.count(Invoice.id))
                .filter(Invoice.invoice_number.like(f"{prefix}%"))
                .scalar()
            )
            next_seq = count + 1
    else:
        next_seq = 1

    return f"{prefix}{next_seq:05d}"


# =========================================================================
# Cost Preview for Service Order
# =========================================================================

def get_order_cost_preview(order_id):
    """Calculate what an invoice would look like without creating one.

    Read-only function that reuses the line-item logic from
    ``generate_from_order()`` but does NOT persist anything.

    Args:
        order_id: The primary key of the service order.

    Returns:
        A dict with keys: ``subtotal``, ``line_items``, ``rush_fee``,
        ``discount``, ``grand_total``.

    Raises:
        ValueError: If the order is not found.
    """
    order = db.session.get(ServiceOrder, order_id)
    if order is None:
        raise ValueError(f"Service order {order_id} not found.")

    line_items = []
    subtotal = Decimal("0.00")

    for order_item in order.order_items.all():
        # Applied services
        for applied_service in order_item.applied_services.all():
            line_total = applied_service.line_total if applied_service.line_total is not None else Decimal("0.00")
            line_items.append({
                "description": applied_service.service_name,
                "quantity": str(applied_service.quantity),
                "unit_price": str(applied_service.unit_price),
                "total": str(line_total),
                "type": "service",
            })
            subtotal += line_total

        # Parts used (non-auto-deducted only)
        for part in order_item.parts_used.all():
            if not part.is_auto_deducted:
                line_total = part.line_total if part.line_total is not None else Decimal("0.00")
                line_items.append({
                    "description": part.inventory_item.name,
                    "quantity": str(part.quantity),
                    "unit_price": str(part.unit_price_at_use),
                    "total": str(line_total),
                    "type": "part",
                })
                subtotal += line_total

        # Labor entries
        for entry in order_item.labor_entries.all():
            tech_name = entry.tech.display_name if entry.tech else "Technician"
            description = f"{tech_name}: {entry.description or 'Labor'}"
            line_total = entry.line_total if entry.line_total is not None else Decimal("0.00")
            line_items.append({
                "description": description,
                "quantity": str(entry.hours),
                "unit_price": str(entry.hourly_rate),
                "total": str(line_total),
                "type": "labor",
            })
            subtotal += line_total

    # Rush fee
    rush_fee = Decimal(str(order.rush_fee)) if order.rush_fee is not None else Decimal("0.00")
    if rush_fee > 0:
        line_items.append({
            "description": "Rush Fee",
            "quantity": "1",
            "unit_price": str(rush_fee),
            "total": str(rush_fee),
            "type": "fee",
        })

    # Discount
    discount_amount = Decimal(str(order.discount_amount)) if order.discount_amount is not None else Decimal("0.00")
    if discount_amount > 0:
        line_items.append({
            "description": "Discount",
            "quantity": "1",
            "unit_price": str(-discount_amount),
            "total": str(-discount_amount),
            "type": "discount",
        })

    grand_total = subtotal + rush_fee - discount_amount

    return {
        "subtotal": str(subtotal),
        "line_items": line_items,
        "rush_fee": str(rush_fee),
        "discount": str(discount_amount),
        "grand_total": str(grand_total),
    }


# =========================================================================
# Generate Invoice from Service Order
# =========================================================================

def generate_from_order(order_id, created_by=None, ip_address=None, user_agent=None):
    """Create an invoice from a service order's data.

    Builds an invoice with line items derived from the order's applied
    services, non-auto-deducted parts, and labor entries.  Adds rush fee
    and discount as separate line items when applicable.

    Args:
        order_id: The primary key of the service order.
        created_by: Optional user ID of the creator.
        ip_address: Optional IP address for audit logging.
        user_agent: Optional user agent for audit logging.

    Returns:
        The newly created Invoice instance.

    Raises:
        ValueError: If the order is not found.
    """
    order = db.session.get(ServiceOrder, order_id)
    if order is None:
        raise ValueError(f"Service order {order_id} not found.")

    # Check for existing invoice linked to this order
    existing = db.session.query(invoice_orders.c.invoice_id).filter(
        invoice_orders.c.order_id == order_id
    ).first()
    if existing:
        raise ValueError(f"Invoice already exists for order {order_id}")

    customer = order.customer

    # Create the invoice
    invoice = Invoice(
        customer_id=customer.id,
        status="draft",
        issue_date=date.today(),
        created_by=created_by,
    )

    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            invoice.invoice_number = generate_invoice_number()
            db.session.add(invoice)
            db.session.flush()  # get invoice.id for line items
            break
        except IntegrityError:
            db.session.rollback()
            if attempt == MAX_RETRIES - 1:
                raise

    sort_order = 0

    # Iterate over order items and build line items
    for order_item in order.order_items.all():
        # Applied services
        for applied_service in order_item.applied_services.all():
            line_total = applied_service.line_total if applied_service.line_total is not None else Decimal("0.00")
            line_item = InvoiceLineItem(
                invoice_id=invoice.id,
                line_type="service",
                description=applied_service.service_name,
                quantity=applied_service.quantity,
                unit_price=applied_service.unit_price,
                line_total=line_total,
                applied_service_id=applied_service.id,
                sort_order=sort_order,
            )
            db.session.add(line_item)
            sort_order += 1

        # Parts used (non-auto-deducted only)
        for part in order_item.parts_used.all():
            if not part.is_auto_deducted:
                line_total = part.line_total if part.line_total is not None else Decimal("0.00")
                line_item = InvoiceLineItem(
                    invoice_id=invoice.id,
                    line_type="part",
                    description=part.inventory_item.name,
                    quantity=part.quantity,
                    unit_price=part.unit_price_at_use,
                    line_total=line_total,
                    parts_used_id=part.id,
                    sort_order=sort_order,
                )
                db.session.add(line_item)
                sort_order += 1

        # Labor entries
        for entry in order_item.labor_entries.all():
            tech_name = entry.tech.display_name if entry.tech else "Technician"
            description = f"{tech_name}: {entry.description or 'Labor'}"
            line_total = entry.line_total if entry.line_total is not None else Decimal("0.00")
            line_item = InvoiceLineItem(
                invoice_id=invoice.id,
                line_type="labor",
                description=description,
                quantity=entry.hours,
                unit_price=entry.hourly_rate,
                line_total=line_total,
                labor_entry_id=entry.id,
                sort_order=sort_order,
            )
            db.session.add(line_item)
            sort_order += 1

    # Rush fee as a line item
    rush_fee = Decimal(str(order.rush_fee)) if order.rush_fee is not None else Decimal("0.00")
    if rush_fee > 0:
        line_item = InvoiceLineItem(
            invoice_id=invoice.id,
            line_type="fee",
            description="Rush Fee",
            quantity=Decimal("1"),
            unit_price=rush_fee,
            line_total=rush_fee,
            sort_order=sort_order,
        )
        db.session.add(line_item)
        sort_order += 1

    # Discount as a line item
    discount_amount = Decimal(str(order.discount_amount)) if order.discount_amount is not None else Decimal("0.00")
    if discount_amount > 0:
        line_item = InvoiceLineItem(
            invoice_id=invoice.id,
            line_type="discount",
            description="Discount",
            quantity=Decimal("1"),
            unit_price=-discount_amount,
            line_total=-discount_amount,
            sort_order=sort_order,
        )
        db.session.add(line_item)
        sort_order += 1

    # Recalculate invoice totals
    db.session.flush()  # ensure all line items are in the session
    invoice.recalculate_totals()

    # Link the order to the invoice via the association table
    db.session.execute(
        invoice_orders.insert().values(
            invoice_id=invoice.id,
            order_id=order.id,
        )
    )

    # Auto-mark $0 invoices as paid
    if invoice.total is not None and invoice.total == 0:
        invoice.status = "paid"
        invoice.paid_date = date.today()
        invoice.balance_due = Decimal("0.00")

    db.session.commit()
    try:
        audit_service.log_action(
            action="create",
            entity_type="invoice",
            entity_id=invoice.id,
            user_id=created_by,
            ip_address=ip_address,
            user_agent=user_agent,
            additional_data=f'{{"from_order_id": {order_id}}}',
        )
    except Exception:
        pass
    return invoice


# =========================================================================
# Line Items
# =========================================================================

def add_line_item(invoice_id, data):
    """Add a line item to an invoice.

    Calculates line_total from quantity and unit_price, then recalculates
    the invoice totals.

    Args:
        invoice_id: The primary key of the invoice.
        data: Dictionary of line item fields.  Expected keys:
            - line_type
            - description
            - quantity
            - unit_price
            Optional keys:
            - applied_service_id
            - labor_entry_id
            - parts_used_id
            - sort_order

    Returns:
        The newly created InvoiceLineItem instance, or None if invoice
        not found.
    """
    invoice = get_invoice(invoice_id)
    if invoice is None:
        return None

    quantity = Decimal(str(data.get("quantity", 1)))
    unit_price = Decimal(str(data["unit_price"]))

    if unit_price < 0 and data["line_type"] != "discount":
        raise ValueError("Unit price must be non-negative for non-discount line items.")

    line_total = quantity * unit_price

    line_item = InvoiceLineItem(
        invoice_id=invoice_id,
        line_type=data["line_type"],
        description=data["description"],
        quantity=quantity,
        unit_price=unit_price,
        line_total=line_total,
        applied_service_id=data.get("applied_service_id"),
        labor_entry_id=data.get("labor_entry_id"),
        parts_used_id=data.get("parts_used_id"),
        sort_order=data.get("sort_order", 0),
    )
    db.session.add(line_item)
    db.session.flush()

    invoice.recalculate_totals()
    db.session.commit()
    try:
        audit_service.log_action(
            action="create",
            entity_type="invoice_line_item",
            entity_id=line_item.id,
            additional_data=f'{{"invoice_id": {invoice_id}}}',
        )
    except Exception:
        pass
    return line_item


def remove_line_item(line_item_id):
    """Remove a line item and recalculate invoice totals.

    Args:
        line_item_id: The primary key of the InvoiceLineItem.

    Returns:
        True if the line item was found and deleted, False otherwise.
    """
    line_item = db.session.get(InvoiceLineItem, line_item_id)
    if line_item is None:
        return False

    invoice = line_item.invoice
    invoice_id = invoice.id
    db.session.delete(line_item)
    db.session.flush()

    invoice.recalculate_totals()
    db.session.commit()
    try:
        audit_service.log_action(
            action="delete",
            entity_type="invoice_line_item",
            entity_id=line_item_id,
            additional_data=f'{{"invoice_id": {invoice_id}}}',
        )
    except Exception:
        pass
    return True


# =========================================================================
# Payments
# =========================================================================

def record_payment(invoice_id, data, recorded_by=None, ip_address=None, user_agent=None):
    """Record a payment against an invoice.

    Creates a Payment record, updates the invoice's amount_paid and
    balance_due, and automatically transitions the invoice status to
    'paid' (if fully paid) or 'partially_paid' (if partially paid).

    Args:
        invoice_id: The primary key of the invoice.
        data: Dictionary of payment fields.  Expected keys:
            - payment_type
            - amount
            - payment_date
            - payment_method
            Optional keys:
            - reference_number
            - notes
        recorded_by: Optional user ID of the person recording the payment.
        ip_address: Optional IP address for audit logging.
        user_agent: Optional user agent for audit logging.

    Returns:
        The newly created Payment instance, or None if invoice not found.
    """
    invoice = get_invoice(invoice_id)
    if invoice is None:
        return None

    payment = Payment(
        invoice_id=invoice_id,
        payment_type=data["payment_type"],
        amount=data["amount"],
        payment_date=data["payment_date"],
        payment_method=data["payment_method"],
        reference_number=data.get("reference_number"),
        notes=data.get("notes"),
        recorded_by=recorded_by,
    )
    db.session.add(payment)
    db.session.flush()

    # Recalculate amount_paid from all payments on this invoice
    # Refunds subtract from the total; all other payment types add.
    total_paid = (
        db.session.query(
            func.coalesce(
                func.sum(
                    case(
                        (Payment.payment_type == "refund", -Payment.amount),
                        else_=Payment.amount,
                    )
                ),
                0,
            )
        )
        .filter(Payment.invoice_id == invoice_id)
        .scalar()
    )
    invoice.amount_paid = Decimal(str(total_paid))
    invoice.balance_due = invoice.total - invoice.amount_paid

    # Update status based on payment
    if invoice.balance_due <= 0:
        invoice.status = "paid"
        invoice.paid_date = date.today()
    elif invoice.amount_paid > 0:
        invoice.status = "partially_paid"

    db.session.commit()
    try:
        audit_service.log_action(
            action="create",
            entity_type="payment",
            entity_id=payment.id,
            user_id=recorded_by,
            field_name="amount",
            new_value=str(data["amount"]),
            ip_address=ip_address,
            user_agent=user_agent,
            additional_data=f'{{"invoice_id": {invoice_id}}}',
        )
    except Exception:
        pass
    try:
        notification_service.notify_payment_received(invoice, payment)
    except Exception:
        pass
    return payment


def get_payments(invoice_id):
    """Return all payments for an invoice.

    Args:
        invoice_id: The primary key of the invoice.

    Returns:
        A list of Payment instances ordered by payment_date.
    """
    return (
        Payment.query
        .filter_by(invoice_id=invoice_id)
        .order_by(Payment.payment_date.asc())
        .all()
    )
