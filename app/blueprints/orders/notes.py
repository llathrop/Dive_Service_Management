"""Orders blueprint — Note routes."""

from flask import flash, redirect, url_for
from flask_security import current_user, login_required, roles_accepted

from app.forms.note import ServiceNoteForm
from app.services import order_service

from app.blueprints.orders import orders_bp


@orders_bp.route("/items/<int:item_id>/notes/add", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def add_note(item_id):
    """Add a note to a service order item."""
    form = ServiceNoteForm()

    if form.validate_on_submit():
        try:
            order_service.add_service_note(
                order_item_id=item_id,
                note_text=form.note_text.data,
                note_type=form.note_type.data,
                created_by=current_user.id,
            )
            flash("Note added.", "success")
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
