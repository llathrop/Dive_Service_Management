"""Report service layer — data aggregation for business reports.

Provides module-level functions for generating revenue, orders,
inventory, customer, and accounts-receivable aging reports.  Each
function returns a plain dict suitable for rendering in templates or
serializing to JSON.

All monetary values are returned as Decimal for precision.
Date-range filters are optional; when omitted the report covers all
available data.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import case, func

from app.extensions import db
from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.parts_used import PartUsed
from app.models.service_order import ServiceOrder
from app.models.user import User


# =========================================================================
# Revenue Report
# =========================================================================

def revenue_report(date_from=None, date_to=None):
    """Aggregate revenue data from paid and partially-paid invoices.

    Sums invoice line items broken down by line_type and provides a
    monthly breakdown for charting.

    Args:
        date_from: Optional start date (inclusive) filtering on
            Invoice.issue_date.
        date_to: Optional end date (inclusive) filtering on
            Invoice.issue_date.

    Returns:
        A dict with keys:
            - total_revenue: Decimal total of invoice totals.
            - parts_revenue: Decimal sum of 'part' line items.
            - labor_revenue: Decimal sum of 'labor' line items.
            - services_revenue: Decimal sum of 'service' line items.
            - fees_revenue: Decimal sum of 'fee' line items.
            - monthly_breakdown: list of dicts with 'month' (YYYY-MM)
              and 'total' (Decimal) keys, ordered chronologically.
    """
    paid_statuses = ("paid", "partially_paid")

    # --- Base filter for paid invoices in date range ---
    def _invoice_filter(query):
        query = query.filter(Invoice.status.in_(paid_statuses))
        if date_from is not None:
            query = query.filter(Invoice.issue_date >= date_from)
        if date_to is not None:
            query = query.filter(Invoice.issue_date <= date_to)
        return query

    # --- Total revenue from invoice totals ---
    total_q = _invoice_filter(
        db.session.query(func.coalesce(func.sum(Invoice.total), 0))
    )
    total_revenue = Decimal(str(total_q.scalar()))

    # --- Revenue by line type ---
    line_q = (
        db.session.query(
            InvoiceLineItem.line_type,
            func.coalesce(func.sum(InvoiceLineItem.line_total), 0),
        )
        .join(Invoice, Invoice.id == InvoiceLineItem.invoice_id)
    )
    line_q = _invoice_filter(line_q)
    line_q = line_q.group_by(InvoiceLineItem.line_type)

    revenue_by_type = {row[0]: Decimal(str(row[1])) for row in line_q.all()}

    parts_revenue = revenue_by_type.get("part", Decimal("0.00"))
    labor_revenue = revenue_by_type.get("labor", Decimal("0.00"))
    services_revenue = revenue_by_type.get("service", Decimal("0.00"))
    fees_revenue = revenue_by_type.get("fee", Decimal("0.00"))

    # --- Monthly breakdown ---
    # Fetch paid invoices and group by month in Python to avoid
    # DB-specific date functions (strftime=SQLite, DATE_FORMAT=MariaDB).
    inv_q = _invoice_filter(
        db.session.query(Invoice.issue_date, Invoice.total)
    )
    monthly_totals: dict[str, Decimal] = {}
    for row in inv_q.all():
        if row.issue_date is not None:
            month_key = row.issue_date.strftime("%Y-%m")
            monthly_totals[month_key] = monthly_totals.get(
                month_key, Decimal("0.00")
            ) + Decimal(str(row.total or 0))

    monthly_breakdown = [
        {"month": m, "total": t}
        for m, t in sorted(monthly_totals.items())
    ]

    return {
        "total_revenue": total_revenue,
        "parts_revenue": parts_revenue,
        "labor_revenue": labor_revenue,
        "services_revenue": services_revenue,
        "fees_revenue": fees_revenue,
        "monthly_breakdown": monthly_breakdown,
    }


# =========================================================================
# Orders Report
# =========================================================================

def orders_report(date_from=None, date_to=None):
    """Aggregate service order statistics.

    Provides counts by status and priority, average turnaround time for
    completed orders, and order counts per assigned technician.

    Args:
        date_from: Optional start date (inclusive) filtering on
            ServiceOrder.date_received.
        date_to: Optional end date (inclusive) filtering on
            ServiceOrder.date_received.

    Returns:
        A dict with keys:
            - total_orders: int count of orders in range.
            - status_breakdown: dict of {status: count}.
            - priority_breakdown: dict of {priority: count}.
            - avg_turnaround_days: float average days from date_received
              to date_completed for completed orders (None if no data).
            - orders_by_tech: list of dicts with 'tech_name' and 'count'.
    """

    # --- Base query (non-deleted orders in date range) ---
    def _order_filter(query):
        query = query.filter(ServiceOrder.is_deleted == False)  # noqa: E712
        if date_from is not None:
            query = query.filter(ServiceOrder.date_received >= date_from)
        if date_to is not None:
            query = query.filter(ServiceOrder.date_received <= date_to)
        return query

    # --- Total orders ---
    total_q = _order_filter(
        db.session.query(func.count(ServiceOrder.id))
    )
    total_orders = total_q.scalar()

    # --- Status breakdown ---
    status_q = _order_filter(
        db.session.query(
            ServiceOrder.status,
            func.count(ServiceOrder.id),
        )
    ).group_by(ServiceOrder.status)
    status_breakdown = {row[0]: row[1] for row in status_q.all()}

    # --- Priority breakdown ---
    priority_q = _order_filter(
        db.session.query(
            ServiceOrder.priority,
            func.count(ServiceOrder.id),
        )
    ).group_by(ServiceOrder.priority)
    priority_breakdown = {row[0]: row[1] for row in priority_q.all()}

    # --- Average turnaround (date_completed - date_received) ---
    # Compute in Python to avoid DB-specific date functions
    # (julianday=SQLite, DATEDIFF=MariaDB).
    turnaround_q = _order_filter(
        db.session.query(
            ServiceOrder.date_received,
            ServiceOrder.date_completed,
        ).filter(ServiceOrder.date_completed.isnot(None))
    )
    turnaround_rows = turnaround_q.all()
    if turnaround_rows:
        total_days = sum(
            (row.date_completed - row.date_received).days
            for row in turnaround_rows
        )
        avg_turnaround_days = round(total_days / len(turnaround_rows), 1)
    else:
        avg_turnaround_days = None

    # --- Orders by technician ---
    # User.display_name is a Python property, so we construct the
    # name from first_name and last_name columns in the SQL query.
    tech_q = _order_filter(
        db.session.query(
            (User.first_name + " " + User.last_name).label("tech_name"),
            func.count(ServiceOrder.id).label("count"),
        )
        .join(User, User.id == ServiceOrder.assigned_tech_id)
    ).group_by(User.first_name, User.last_name).order_by(
        func.count(ServiceOrder.id).desc()
    )

    orders_by_tech = [
        {"tech_name": row.tech_name, "count": row.count}
        for row in tech_q.all()
    ]

    return {
        "total_orders": total_orders,
        "status_breakdown": status_breakdown,
        "priority_breakdown": priority_breakdown,
        "avg_turnaround_days": avg_turnaround_days,
        "orders_by_tech": orders_by_tech,
    }


# =========================================================================
# Inventory Report
# =========================================================================

def inventory_report():
    """Aggregate inventory statistics.

    Provides stock counts, total valuation, low/out-of-stock counts,
    category breakdown, and the most-used parts by quantity consumed.

    Returns:
        A dict with keys:
            - total_items: int count of active inventory items.
            - total_value: Decimal sum of (quantity_in_stock * purchase_cost).
            - low_stock_items: list of InventoryItem instances below
              reorder_level.
            - out_of_stock_count: int count where quantity_in_stock <= 0.
            - category_breakdown: dict of {category: count}.
            - most_used_parts: list of dicts with 'item_id', 'name',
              and 'total_used' keys (top 10 by usage).
    """
    base_filter = (
        (InventoryItem.is_active == True)  # noqa: E712
        & (InventoryItem.is_deleted == False)  # noqa: E712
    )

    # --- Total active items ---
    total_items = (
        db.session.query(func.count(InventoryItem.id))
        .filter(base_filter)
        .scalar()
    )

    # --- Total inventory value ---
    total_value_raw = (
        db.session.query(
            func.coalesce(
                func.sum(
                    InventoryItem.quantity_in_stock * InventoryItem.purchase_cost
                ),
                0,
            )
        )
        .filter(base_filter)
        .scalar()
    )
    total_value = Decimal(str(total_value_raw))

    # --- Low stock items (below reorder_level, reorder_level > 0) ---
    low_stock_items = (
        InventoryItem.query
        .filter(
            base_filter,
            InventoryItem.reorder_level > 0,
            InventoryItem.quantity_in_stock <= InventoryItem.reorder_level,
        )
        .order_by(InventoryItem.quantity_in_stock.asc())
        .all()
    )

    # --- Out of stock count ---
    out_of_stock_count = (
        db.session.query(func.count(InventoryItem.id))
        .filter(base_filter, InventoryItem.quantity_in_stock <= 0)
        .scalar()
    )

    # --- Category breakdown ---
    category_q = (
        db.session.query(
            InventoryItem.category,
            func.count(InventoryItem.id),
        )
        .filter(base_filter)
        .group_by(InventoryItem.category)
        .order_by(InventoryItem.category)
    )
    category_breakdown = {row[0]: row[1] for row in category_q.all()}

    # --- Most used parts (top 10 by total quantity consumed) ---
    most_used_q = (
        db.session.query(
            InventoryItem.id.label("item_id"),
            InventoryItem.name.label("name"),
            func.sum(PartUsed.quantity).label("total_used"),
        )
        .join(PartUsed, PartUsed.inventory_item_id == InventoryItem.id)
        .filter(base_filter)
        .group_by(InventoryItem.id, InventoryItem.name)
        .order_by(func.sum(PartUsed.quantity).desc())
        .limit(10)
    )
    most_used_parts = [
        {
            "item_id": row.item_id,
            "name": row.name,
            "total_used": Decimal(str(row.total_used)),
        }
        for row in most_used_q.all()
    ]

    return {
        "total_items": total_items,
        "total_value": total_value,
        "low_stock_items": low_stock_items,
        "out_of_stock_count": out_of_stock_count,
        "category_breakdown": category_breakdown,
        "most_used_parts": most_used_parts,
    }


# =========================================================================
# Customer Report
# =========================================================================

def customer_report(date_from=None, date_to=None):
    """Aggregate customer statistics.

    Provides total and new customer counts and identifies the top
    customers by total invoice value.

    Args:
        date_from: Optional start date (inclusive) for counting new
            customers (filtering on Customer.created_at).
        date_to: Optional end date (inclusive) for counting new
            customers (filtering on Customer.created_at).

    Returns:
        A dict with keys:
            - total_customers: int count of non-deleted customers.
            - new_customers: int count of customers created in the
              given date range.
            - top_customers: list of dicts with 'customer_id',
              'display_name', and 'total_value' (Decimal) keys,
              top 10 by total invoice value.
    """
    # --- Total customers (non-deleted) ---
    total_customers = (
        db.session.query(func.count(Customer.id))
        .filter(Customer.is_deleted == False)  # noqa: E712
        .scalar()
    )

    # --- New customers in date range ---
    new_q = (
        db.session.query(func.count(Customer.id))
        .filter(Customer.is_deleted == False)  # noqa: E712
    )
    if date_from is not None:
        new_q = new_q.filter(Customer.created_at >= date_from)
    if date_to is not None:
        new_q = new_q.filter(Customer.created_at <= date_to)
    new_customers = new_q.scalar()

    # --- Top 10 customers by invoice value ---
    # Use case expression to build display_name at the SQL level
    display_name_expr = case(
        (
            Customer.business_name.isnot(None),
            Customer.business_name,
        ),
        else_=(Customer.first_name + " " + Customer.last_name),
    )

    top_q = (
        db.session.query(
            Customer.id.label("customer_id"),
            display_name_expr.label("display_name"),
            func.coalesce(func.sum(Invoice.total), 0).label("total_value"),
        )
        .join(Invoice, Invoice.customer_id == Customer.id)
        .filter(
            Customer.is_deleted == False,  # noqa: E712
            Invoice.status != "void",
        )
        .group_by(Customer.id, display_name_expr)
        .order_by(func.sum(Invoice.total).desc())
        .limit(10)
    )
    top_customers = [
        {
            "customer_id": row.customer_id,
            "display_name": row.display_name,
            "total_value": Decimal(str(row.total_value)),
        }
        for row in top_q.all()
    ]

    return {
        "total_customers": total_customers,
        "new_customers": new_customers,
        "top_customers": top_customers,
    }


# =========================================================================
# Accounts Receivable Aging Report
# =========================================================================

def aging_report():
    """Generate an accounts-receivable aging report.

    Groups unpaid invoices into aging buckets based on how many days
    past due_date they are relative to today.  Invoices with status
    'paid', 'void', or 'refunded' are excluded.

    Returns:
        A dict with key 'buckets', a list of dicts each containing:
            - label: str description of the aging bucket.
            - count: int number of invoices in this bucket.
            - total_amount: Decimal sum of balance_due for the bucket.
    """
    today = date.today()
    excluded_statuses = ("paid", "void", "refunded")

    # Fetch all unpaid invoices
    unpaid = (
        Invoice.query
        .filter(Invoice.status.notin_(excluded_statuses))
        .all()
    )

    # Initialize buckets
    buckets = [
        {"label": "Current", "count": 0, "total_amount": Decimal("0.00")},
        {"label": "1-30 days", "count": 0, "total_amount": Decimal("0.00")},
        {"label": "31-60 days", "count": 0, "total_amount": Decimal("0.00")},
        {"label": "61-90 days", "count": 0, "total_amount": Decimal("0.00")},
        {"label": "90+ days", "count": 0, "total_amount": Decimal("0.00")},
    ]

    for inv in unpaid:
        balance = Decimal(str(inv.balance_due)) if inv.balance_due is not None else Decimal("0.00")

        # Determine days overdue
        if inv.due_date is None or inv.due_date >= today:
            # Not overdue — Current
            idx = 0
        else:
            days_overdue = (today - inv.due_date).days
            if days_overdue <= 30:
                idx = 1
            elif days_overdue <= 60:
                idx = 2
            elif days_overdue <= 90:
                idx = 3
            else:
                idx = 4

        buckets[idx]["count"] += 1
        buckets[idx]["total_amount"] += balance

    return {"buckets": buckets}
