"""Orders blueprint — Status change routes."""

from flask import flash, jsonify, redirect, request, url_for
from flask_security import current_user, login_required, roles_accepted

from app.services import order_service

from app.blueprints.orders import orders_bp


@orders_bp.route("/<int:id>/kanban-status", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def kanban_change_status(id):
    """Change order status via AJAX from the Kanban board."""
    new_status = request.form.get("new_status", "").strip()
    if not new_status:
        return jsonify({"error": "No status provided."}), 400

    order, success = order_service.change_status(
        id, new_status, current_user.id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string,
    )
    if success:
        return jsonify({
            "success": True,
            "order_id": order.id,
            "new_status": order.status,
            "display_status": order.display_status,
        }), 200
    else:
        return jsonify({
            "error": (
                f"Cannot transition from '{order.display_status}' "
                f"to '{new_status.replace('_', ' ').title()}'."
            ),
        }), 400


@orders_bp.route("/<int:id>/status", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def change_status(id):
    """Transition a service order to a new status."""
    new_status = request.form.get("new_status", "").strip()
    if not new_status:
        flash("No status provided.", "error")
        return redirect(url_for("orders.detail", id=id))

    order, success = order_service.change_status(
        id, new_status, current_user.id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string,
    )
    if success:
        flash(f"Order status changed to {order.display_status}.", "success")
    else:
        flash(
            f"Cannot transition from '{order.display_status}' "
            f"to '{new_status.replace('_', ' ').title()}'.",
            "error",
        )
    return redirect(url_for("orders.detail", id=id))
