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
    providers = shipping_service.get_provider_catalog()
    default_provider_code = shipping_service.get_workflow_default_provider_code()

    return render_template(
        "orders/shipping.html",
        order=order,
        shipments=shipments,
        shipping_total=shipping_total,
        providers=providers,
        default_provider_code=default_provider_code,
        quote_placeholder=_get_quote_placeholder(default_provider_code),
        default_destination_postal_code=(order.customer.postal_code or ""),
        default_destination_country=(order.customer.country or "US"),
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
    provider_code = request.form.get("provider_code") or None
    shipping_method = request.form.get("shipping_method") or None
    destination_postal_code = request.form.get("destination_postal_code") or None
    destination_country = request.form.get("destination_country") or None
    carrier = request.form.get("carrier") or None
    tracking_number = request.form.get("tracking_number") or None
    notes = request.form.get("notes") or None

    try:
        shipping_service.create_shipment(
            order_id=order.id,
            weight_lbs=weight_lbs,
            length_in=length_in,
            width_in=width_in,
            height_in=height_in,
            shipping_method=shipping_method,
            provider_code=provider_code,
            destination_postal_code=destination_postal_code,
            destination_country=destination_country,
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
    get_order(id)

    provider_code = request.args.get("provider_code") or None
    method = request.args.get("shipping_method") or request.args.get("method")
    weight_lbs = _parse_decimal(request.args.get("weight_lbs"))
    length_in = _parse_decimal(request.args.get("length_in"))
    width_in = _parse_decimal(request.args.get("width_in"))
    height_in = _parse_decimal(request.args.get("height_in"))
    destination_postal_code = request.args.get("destination_postal_code") or None
    destination_country = request.args.get("destination_country") or None

    try:
        requires_weight = shipping_service.provider_requires_weight(provider_code, method)
    except ValueError as exc:
        return render_template(
            "partials/shipping_quote.html",
            quote=None,
            placeholder_text=str(exc),
        )

    if requires_weight and (weight_lbs is None or weight_lbs <= 0):
        return render_template(
            "partials/shipping_quote.html",
            quote=None,
            placeholder_text=_get_quote_placeholder(provider_code, method),
        )

    try:
        quote = shipping_service.quote_shipping(
            weight_lbs=weight_lbs,
            length_in=length_in,
            width_in=width_in,
            height_in=height_in,
            method=method,
            provider_code=provider_code,
            destination_postal_code=destination_postal_code,
            destination_country=destination_country,
        )
    except ValueError as exc:
        return render_template(
            "partials/shipping_quote.html",
            quote=None,
            placeholder_text=str(exc),
        )

    return render_template(
        "partials/shipping_quote.html",
        quote=quote.to_dict(),
        placeholder_text=_get_quote_placeholder(provider_code, method),
    )


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


def _get_quote_placeholder(provider_code=None, shipping_method=None):
    """Return contextual placeholder text for the selected provider."""
    try:
        if shipping_service.provider_requires_weight(provider_code, shipping_method):
            return "Enter weight and optional dimensions to estimate shipping."
    except ValueError:
        pass
    return "Local pickup stays at $0.00 and does not require package weight."
