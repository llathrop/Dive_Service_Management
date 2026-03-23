"""Admin blueprint — Audit log routes."""

import csv
import io

from flask import render_template, request, Response, stream_with_context
from flask_security import roles_required

from app.blueprints.admin import admin_bp

# Fields whose old/new values must never appear in exports
SENSITIVE_FIELDS = {"password", "password_hash", "fs_uniquifier", "tf_totp_secret"}


@admin_bp.route("/audit-log")
@roles_required("admin")
def audit_log():
    """View the audit log with filtering and pagination."""
    from app.services import audit_service
    from app.models.user import User

    f = _parse_audit_filters()
    page = request.args.get("page", 1, type=int)

    pagination = audit_service.get_audit_logs(
        entity_type=f["entity_type"],
        entity_id=None,
        user_id=f["user_id"],
        action=f["action"],
        date_from=f["date_from"],
        date_to=f["date_to"],
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
            "entity_type": f["entity_type"] or "",
            "action": f["action"] or "",
            "user_id": f["user_id"] or "",
            "date_from": f["date_from_str"],
            "date_to": f["date_to_str"],
        },
    )


def _parse_audit_filters():
    """Parse audit log filter parameters from the request query string.

    Returns a dict with keys: entity_type, action, user_id, date_from,
    date_to, date_from_str, date_to_str.  The *_str variants are the raw
    query-string values (for repopulating form fields).
    """
    from datetime import datetime

    entity_type = request.args.get("entity_type", "").strip() or None
    action = request.args.get("action", "").strip() or None
    user_id = request.args.get("user_id", type=int)

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

    return {
        "entity_type": entity_type,
        "action": action,
        "user_id": user_id,
        "date_from": date_from,
        "date_to": date_to,
        "date_from_str": date_from_str,
        "date_to_str": date_to_str,
    }


def _csv_row(row):
    """Convert a list of values to a CSV-formatted string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(row)
    return output.getvalue()


@admin_bp.route("/audit-log/export")
@roles_required("admin")
def audit_log_export():
    """Export audit log entries as a streaming CSV download."""
    from sqlalchemy import and_
    from app.models.audit_log import AuditLog

    f = _parse_audit_filters()

    query = AuditLog.query

    filters = []
    if f["entity_type"]:
        filters.append(AuditLog.entity_type == f["entity_type"])
    if f["user_id"] is not None:
        filters.append(AuditLog.user_id == f["user_id"])
    if f["action"]:
        filters.append(AuditLog.action == f["action"])
    if f["date_from"]:
        filters.append(AuditLog.created_at >= f["date_from"])
    if f["date_to"]:
        filters.append(AuditLog.created_at <= f["date_to"])

    if filters:
        query = query.filter(and_(*filters))

    query = query.order_by(AuditLog.created_at.desc())

    headers = [
        "Timestamp", "User", "Action", "Entity Type", "Entity ID", "Details",
    ]

    def generate():
        yield "\ufeff" + _csv_row(headers)
        for entry in query.yield_per(100):
            details = ""
            if entry.field_name and entry.field_name in SENSITIVE_FIELDS:
                details = f"{entry.field_name}: [REDACTED]"
            elif entry.field_name:
                details = f"{entry.field_name}: {entry.old_value or ''} -> {entry.new_value or ''}"
            elif entry.additional_data:
                details = entry.additional_data
            yield _csv_row([
                entry.created_at.isoformat() if entry.created_at else "",
                entry.user.username if entry.user else "System",
                entry.action,
                entry.entity_type,
                entry.entity_id,
                details,
            ])

    return Response(
        stream_with_context(generate()),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=audit_log.csv",
        },
    )
