"""Orders blueprint — Applied service routes."""

from flask import flash, redirect, url_for
from flask_security import current_user, login_required, roles_accepted

from app.extensions import db
from app.forms.applied_service import AppliedServiceForm
from app.models.price_list import PriceListItem
from app.services import order_service

from app.blueprints.orders import orders_bp


@orders_bp.route("/items/<int:item_id>/services/add", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def add_service(item_id):
    """Add an applied service to a service order item."""
    form = AppliedServiceForm()

    # Populate choices so validation passes
    price_items = PriceListItem.query.filter_by(is_active=True).order_by(PriceListItem.name).all()
    form.price_list_item_id.choices = [
        ("", "-- Select (or leave blank for custom) --")
    ] + [(pi.id, pi.name) for pi in price_items]

    if form.validate_on_submit():
        data = {
            "price_list_item_id": form.price_list_item_id.data,
            "service_name": form.service_name.data,
            "service_description": form.service_description.data,
            "quantity": form.quantity.data,
            "unit_price": form.unit_price.data,
            "discount_percent": form.discount_percent.data,
            "is_taxable": form.is_taxable.data,
            "notes": form.notes.data,
        }
        order_service.add_applied_service(item_id, data, added_by=current_user.id)
        flash("Service added.", "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", "error")

    # Navigate back to the parent order's detail page
    order_item = order_service.get_order_item(item_id)
    order_id = order_item.order_id if order_item else None
    if order_id:
        return redirect(url_for("orders.detail", id=order_id))
    return redirect(url_for("orders.list_orders"))


@orders_bp.route("/services/<int:service_id>/remove", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def remove_service(service_id):
    """Remove an applied service from a service order item."""
    from app.models.applied_service import AppliedService

    applied = db.session.get(AppliedService, service_id)
    if applied is None:
        flash("Applied service not found.", "error")
        return redirect(url_for("orders.list_orders"))

    # Get the order_id before deletion
    order_item = order_service.get_order_item(applied.service_order_item_id)
    order_id = order_item.order_id if order_item else None

    order_service.remove_applied_service(service_id)
    flash("Service removed.", "success")

    if order_id:
        return redirect(url_for("orders.detail", id=order_id))
    return redirect(url_for("orders.list_orders"))
