"""Orders blueprint — Part routes."""

from flask import flash, redirect, url_for
from flask_security import current_user, login_required, roles_accepted

from app.extensions import db
from app.forms.parts_used import PartUsedForm
from app.models.inventory import InventoryItem
from app.services import order_service

from app.blueprints.orders import orders_bp


@orders_bp.route("/items/<int:item_id>/parts/add", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def add_part(item_id):
    """Add a part (inventory item) to a service order item."""
    form = PartUsedForm()

    # Populate choices so validation passes
    inv_items = (
        InventoryItem.not_deleted()
        .filter_by(is_active=True)
        .order_by(InventoryItem.name)
        .all()
    )
    form.inventory_item_id.choices = [("", "-- Select --")] + [
        (ii.id, ii.name) for ii in inv_items
    ]

    if form.validate_on_submit():
        try:
            order_service.add_part_used(
                order_item_id=item_id,
                inventory_item_id=form.inventory_item_id.data,
                quantity=form.quantity.data,
                unit_price_at_use=form.unit_price_at_use.data,
                notes=form.notes.data,
                added_by=current_user.id,
            )
            flash("Part added.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
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


@orders_bp.route("/parts/<int:part_id>/remove", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def remove_part(part_id):
    """Remove a part used record and restore inventory."""
    from app.models.parts_used import PartUsed

    part = db.session.get(PartUsed, part_id)
    if part is None:
        flash("Part record not found.", "error")
        return redirect(url_for("orders.list_orders"))

    # Get the order_id before deletion
    order_item = order_service.get_order_item(part.service_order_item_id)
    order_id = order_item.order_id if order_item else None

    order_service.remove_part_used(part_id)
    flash("Part removed.", "success")

    if order_id:
        return redirect(url_for("orders.detail", id=order_id))
    return redirect(url_for("orders.list_orders"))
