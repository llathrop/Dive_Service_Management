"""Orders blueprint — Labor entry routes."""

from flask import flash, redirect, url_for
from flask_security import current_user, login_required, roles_accepted

from app.extensions import db
from app.forms.labor import LaborEntryForm
from app.services import order_service

from app.blueprints.orders import orders_bp, _get_tech_choices


@orders_bp.route("/items/<int:item_id>/labor/add", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def add_labor(item_id):
    """Add a labor entry to a service order item."""
    form = LaborEntryForm()

    # Populate choices so validation passes
    form.tech_id.choices = [("", "-- Select --")] + _get_tech_choices()

    if form.validate_on_submit():
        try:
            order_service.add_labor_entry(
                order_item_id=item_id,
                tech_id=form.tech_id.data,
                hours=form.hours.data,
                hourly_rate=form.hourly_rate.data,
                description=form.description.data,
                work_date=form.work_date.data,
            )
            flash("Labor entry added.", "success")
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


@orders_bp.route("/labor/<int:labor_id>/remove", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def remove_labor(labor_id):
    """Remove a labor entry."""
    from app.models.labor import LaborEntry

    entry = db.session.get(LaborEntry, labor_id)
    if entry is None:
        flash("Labor entry not found.", "error")
        return redirect(url_for("orders.list_orders"))

    # Get the order_id before deletion
    order_item = order_service.get_order_item(entry.service_order_item_id)
    order_id = order_item.order_id if order_item else None

    order_service.remove_labor_entry(labor_id)
    flash("Labor entry removed.", "success")

    if order_id:
        return redirect(url_for("orders.detail", id=order_id))
    return redirect(url_for("orders.list_orders"))
