"""Dashboard blueprint.

Provides the main landing page for authenticated users with live
summary cards showing open orders, pickup queue, low stock alerts,
and overdue invoices, plus a live activity feed from the audit log.
"""

from datetime import date

from flask import Blueprint, render_template
from flask_security import login_required
from sqlalchemy import func

from app.extensions import db
from app.models.inventory import InventoryItem
from app.models.invoice import Invoice
from app.models.service_order import ServiceOrder
from app.services import audit_service

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

# Statuses that count as "open" (not yet picked up or cancelled)
OPEN_ORDER_STATUSES = (
    "intake",
    "assessment",
    "awaiting_approval",
    "in_progress",
    "awaiting_parts",
    "completed",
    "ready_for_pickup",
)


@dashboard_bp.route("/")
@login_required
def index():
    """Render the main dashboard view with live summary counts."""
    # Open orders count
    open_orders = (
        db.session.query(func.count(ServiceOrder.id))
        .filter(
            ServiceOrder.is_deleted == False,  # noqa: E712
            ServiceOrder.status.in_(OPEN_ORDER_STATUSES),
        )
        .scalar()
    )

    # Awaiting pickup count
    awaiting_pickup = (
        db.session.query(func.count(ServiceOrder.id))
        .filter(
            ServiceOrder.is_deleted == False,  # noqa: E712
            ServiceOrder.status == "ready_for_pickup",
        )
        .scalar()
    )

    # Low stock count (active items below reorder level)
    low_stock_count = (
        db.session.query(func.count(InventoryItem.id))
        .filter(
            InventoryItem.is_active == True,  # noqa: E712
            InventoryItem.is_deleted == False,  # noqa: E712
            InventoryItem.reorder_level > 0,
            InventoryItem.quantity_in_stock <= InventoryItem.reorder_level,
        )
        .scalar()
    )

    # Overdue invoices count
    today = date.today()
    overdue_invoices = (
        db.session.query(func.count(Invoice.id))
        .filter(
            Invoice.status.notin_(("paid", "void", "refunded")),
            Invoice.due_date < today,
        )
        .scalar()
    )

    recent_activity = audit_service.get_recent_activity(limit=15)

    return render_template(
        "dashboard/index.html",
        open_orders=open_orders,
        awaiting_pickup=awaiting_pickup,
        low_stock_count=low_stock_count,
        overdue_invoices=overdue_invoices,
        recent_activity=recent_activity,
    )


@dashboard_bp.route("/activity-feed")
@login_required
def activity_feed():
    """Return the activity feed HTML fragment for HTMX polling."""
    recent_activity = audit_service.get_recent_activity(limit=15)
    return render_template(
        "dashboard/_activity_feed.html",
        recent_activity=recent_activity,
    )
