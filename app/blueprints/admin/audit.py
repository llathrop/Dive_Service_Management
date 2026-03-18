"""Admin blueprint — Audit log routes."""

from flask import render_template, request
from flask_security import roles_required

from app.blueprints.admin import admin_bp


@admin_bp.route("/audit-log")
@roles_required("admin")
def audit_log():
    """View the audit log with filtering and pagination."""
    from datetime import datetime
    from app.services import audit_service
    from app.models.user import User

    # Parse filter parameters
    entity_type = request.args.get("entity_type", "").strip() or None
    action = request.args.get("action", "").strip() or None
    user_id = request.args.get("user_id", type=int)
    page = request.args.get("page", 1, type=int)

    date_from = None
    date_from_str = request.args.get("date_from", "").strip()
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, "%Y-%m-%d")
        except ValueError:
            pass

    date_to = None
    date_to_str = request.args.get("date_to", "").strip()
    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
        except ValueError:
            pass

    pagination = audit_service.get_audit_logs(
        entity_type=entity_type,
        entity_id=None,
        user_id=user_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=50,
    )

    users = User.query.order_by(User.username).all()

    entity_types = [
        "customer", "service_order", "service_item", "inventory_item",
        "invoice", "payment", "price_list_item", "user",
    ]
    actions = [
        "create", "update", "delete", "restore", "login", "logout",
        "export", "status_change",
    ]

    return render_template(
        "admin/audit_log.html",
        pagination=pagination,
        logs=pagination.items,
        users=users,
        entity_types=entity_types,
        actions=actions,
        filters={
            "entity_type": entity_type or "",
            "action": action or "",
            "user_id": user_id or "",
            "date_from": date_from_str,
            "date_to": date_to_str,
        },
    )
