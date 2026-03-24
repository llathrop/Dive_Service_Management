"""Shipping sub-routes for the orders blueprint.

Provides routes for managing shipments on service orders: creating,
updating, deleting shipments, and an HTMX endpoint for real-time
cost estimation.
"""

from decimal import Decimal, InvalidOperation

from flask import flash, redirect, render_template, request, url_for
from flask_security import current_user, login_required, roles_accepted

from app.blueprints.orders import orders_bp
from app.services import shipping_service
from app.services.order_service import get_order
from app.models.shipment import VALID_STATUSES


# ======================================================================
# Shipping management page
# ======================================================================


@orders_bp.route("/<int:id>/shipping")
@login_required
@roles_accepted("admin", "technician")
def shipping(id):
    """Display shipping management page for an order."""
    order = get_order(id)
    shipments = shipping_service.get_order_shipments(id)
    shipping_total = shipping_service.get_order_shipping_total(id)
    provider = shipping_service.get_provider()
    methods = provider.get_available_methods()

    return render_template(
        "orders/shipping.html",
        order=order,
        shipments=shipments,
        shipping_total=shipping_total,
        methods=methods,
    )


# ======================================================================
# Create shipment
# ======================================================================


@orders_bp.route("/<int:id>/shipping", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def create_shipment(id):
    """Create a new shipment for an order."""
    order = get_order(id)

    weight_lbs = _parse_decimal(request.form.get("weight_lbs"))
    length_in = _parse_decimal(request.form.get("length_in"))
    width_in = _parse_decimal(request.form.get("width_in"))
    height_in = _parse_decimal(request.form.get("height_in"))
    shipping_method = request.form.get("shipping_method") or None
    carrier = request.form.get("carrier") or None
    tracking_number = request.form.get("tracking_number") or None
    notes = request.form.get("notes") or None

    if weight_lbs is None or weight_lbs <= 0:
        flash("Weight is required and must be greater than zero.", "error")
        return redirect(url_for("orders.shipping", id=id))

    try:
        shipping_service.create_shipment(
            order_id=order.id,
            weight_lbs=weight_lbs,
            length_in=length_in,
            width_in=width_in,
            height_in=height_in,
            shipping_method=shipping_method,
            carrier=carrier,
            tracking_number=tracking_number,
            notes=notes,
            user_id=current_user.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
        )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("orders.shipping", id=id))

    flash("Shipment created successfully.", "success")
    return redirect(url_for("orders.shipping", id=id))


# ======================================================================
# HTMX cost estimate endpoint
# ======================================================================


@orders_bp.route("/<int:id>/shipping/estimate")
@login_required
@roles_accepted("admin", "technician")
def shipping_estimate(id):
    """Return an HTML fragment with the estimated shipping cost.

    Accepts weight_lbs as a query parameter. Returns a styled cost
    fragment for HTMX to swap into the page.
    """
    weight_lbs = _parse_decimal(request.args.get("weight_lbs"))

    if weight_lbs is None or weight_lbs <= 0:
        return '<span class="text-muted">Enter weight to estimate cost</span>'

    length_in = _parse_decimal(request.args.get("length_in"))
    width_in = _parse_decimal(request.args.get("width_in"))
    height_in = _parse_decimal(request.args.get("height_in"))
    method = request.args.get("shipping_method") or request.args.get("method")

    cost = shipping_service.estimate_shipping(
        weight_lbs, length_in, width_in, height_in, method,
    )

    return f'<span class="text-success fw-bold">${cost:.2f}</span>'


# ======================================================================
# Update shipment
# ======================================================================


@orders_bp.route("/<int:id>/shipping/<int:shipment_id>/update", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def update_shipment(id, shipment_id):
    """Update tracking info and status for a shipment."""
    get_order(id)  # Verify order exists
    shipping_service.get_shipment_for_order(id, shipment_id)

    kwargs = {}
    if request.form.get("tracking_number") is not None:
        kwargs["tracking_number"] = request.form.get("tracking_number") or None
    if request.form.get("carrier") is not None:
        kwargs["carrier"] = request.form.get("carrier") or None
    if request.form.get("status"):
        status = request.form.get("status")
        if status not in VALID_STATUSES:
            flash("Invalid shipment status.", "error")
            return redirect(url_for("orders.shipping", id=id))
        kwargs["status"] = status
    if request.form.get("notes") is not None:
        kwargs["notes"] = request.form.get("notes") or None

    try:
        shipping_service.update_shipment(
            shipment_id,
            user_id=current_user.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
            **kwargs,
        )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("orders.shipping", id=id))

    flash("Shipment updated successfully.", "success")
    return redirect(url_for("orders.shipping", id=id))


# ======================================================================
# Delete shipment
# ======================================================================


@orders_bp.route("/<int:id>/shipping/<int:shipment_id>/delete", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def delete_shipment(id, shipment_id):
    """Delete a shipment record."""
    get_order(id)  # Verify order exists
    shipping_service.get_shipment_for_order(id, shipment_id)

    shipping_service.delete_shipment(
        shipment_id,
        user_id=current_user.id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string,
    )

    flash("Shipment deleted.", "success")
    return redirect(url_for("orders.shipping", id=id))


# ======================================================================
# Helpers
# ======================================================================


def _parse_decimal(value):
    """Parse a string to Decimal, returning None on failure."""
    if not value:
        return None
    try:
        parsed = Decimal(value.strip())
        if not parsed.is_finite():
            return None
        return parsed
    except (InvalidOperation, ValueError, AttributeError):
        return None
