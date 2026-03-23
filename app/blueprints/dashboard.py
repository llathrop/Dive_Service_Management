"""Dashboard blueprint.

Provides the main landing page for authenticated users with live
summary cards showing open orders, pickup queue, low stock alerts,
and overdue invoices, plus a live activity feed from the audit log.
Supports per-user card visibility and ordering customization.
"""

import json
from datetime import date

from flask import Blueprint, jsonify, render_template, request
from flask_security import current_user, login_required
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

# Available dashboard cards with metadata
DASHBOARD_CARDS = [
    {"id": "open_orders", "title": "Open Orders", "icon": "bi-clipboard-check"},
    {"id": "awaiting_pickup", "title": "Awaiting Pickup", "icon": "bi-bag-check"},
    {"id": "low_stock", "title": "Low Stock Alerts", "icon": "bi-exclamation-triangle"},
    {"id": "overdue_invoices", "title": "Overdue Invoices", "icon": "bi-cash-stack"},
    {"id": "recent_activity", "title": "Recent Activity", "icon": "bi-activity"},
]

DEFAULT_CARD_IDS = [card["id"] for card in DASHBOARD_CARDS]


def _get_dashboard_config(user):
    """Parse user's dashboard_config JSON or return defaults."""
    if user.dashboard_config:
        try:
            config = json.loads(user.dashboard_config)
            visible = config.get("visible_cards", DEFAULT_CARD_IDS)
            card_order = config.get("card_order", DEFAULT_CARD_IDS)
            return {"visible_cards": visible, "card_order": card_order}
        except (json.JSONDecodeError, TypeError):
            pass
    return {"visible_cards": list(DEFAULT_CARD_IDS), "card_order": list(DEFAULT_CARD_IDS)}


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

    # Get user's dashboard config
    config = _get_dashboard_config(current_user)

    return render_template(
        "dashboard/index.html",
        open_orders=open_orders,
        awaiting_pickup=awaiting_pickup,
        low_stock_count=low_stock_count,
        overdue_invoices=overdue_invoices,
        recent_activity=recent_activity,
        dashboard_config=config,
        dashboard_cards=DASHBOARD_CARDS,
    )


@dashboard_bp.route("/config", methods=["POST"])
@login_required
def update_config():
    """Save the user's dashboard card visibility and ordering preferences."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    # Validate that visible_cards and card_order contain only known card IDs
    valid_ids = {c["id"] for c in DASHBOARD_CARDS}
    visible = data.get("visible_cards", DEFAULT_CARD_IDS)
    card_order = data.get("card_order", DEFAULT_CARD_IDS)

    visible = [c for c in visible if c in valid_ids]
    card_order = [c for c in card_order if c in valid_ids]

    config = {"visible_cards": visible, "card_order": card_order}
    current_user.dashboard_config = json.dumps(config)
    db.session.commit()
    return jsonify({"status": "ok"})


@dashboard_bp.route("/activity-feed")
@login_required
def activity_feed():
    """Return the activity feed HTML fragment for HTMX polling."""
    recent_activity = audit_service.get_recent_activity(limit=15)
    return render_template(
        "dashboard/_activity_feed.html",
        recent_activity=recent_activity,
    )
