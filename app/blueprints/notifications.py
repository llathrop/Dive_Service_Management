"""Notifications blueprint — in-app notification management."""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_security import current_user, login_required

from app.services import notification_service

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/")
@login_required
def list_notifications():
    """List all notifications for the current user."""
    page = request.args.get("page", 1, type=int)
    unread_only = request.args.get("unread_only", False, type=bool)
    notifications = notification_service.get_notifications(
        current_user.id, unread_only=unread_only, page=page
    )
    return render_template(
        "notifications/list.html",
        notifications=notifications,
        unread_only=unread_only,
    )


@notifications_bp.route("/count")
@login_required
def unread_count():
    """Return unread notification count as JSON (for HTMX polling)."""
    count = notification_service.get_unread_count(current_user.id)
    return jsonify({"count": count})


@notifications_bp.route("/<int:id>/read", methods=["POST"])
@login_required
def mark_read(id):
    """Mark a notification as read."""
    notification_service.mark_as_read(id, user_id=current_user.id)
    if request.headers.get("HX-Request"):
        return ""  # HTMX - return empty for swap
    return redirect(url_for("notifications.list_notifications"))


@notifications_bp.route("/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    """Mark all notifications as read."""
    notification_service.mark_all_read(current_user.id)
    flash("All notifications marked as read.", "success")
    return redirect(url_for("notifications.list_notifications"))
