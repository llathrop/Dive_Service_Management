"""Service Items blueprint.

Provides routes for listing, creating, viewing, editing, and soft-deleting
service items (customer-owned dive equipment).  Supports drysuit-specific
detail fields via the DrysuitDetails model.  All routes require
authentication.  Write operations require the 'admin' or 'technician' role.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_security import current_user, login_required, roles_accepted
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms.item import DrysuitDetailsForm, ServiceItemForm
from app.models.drysuit_details import DrysuitDetails
from app.models.service_item import ServiceItem
from app.services import audit_service

items_bp = Blueprint("items", __name__, url_prefix="/items")

# Columns that the list view is allowed to sort by.
SORTABLE_FIELDS = {
    "name", "serial_number", "item_category", "brand", "model",
    "serviceability", "year_manufactured", "created_at",
}


@items_bp.route("/")
@login_required
def list_items():
    """List service items with pagination and search."""
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "")
    sort = request.args.get("sort", "name")
    order = request.args.get("order", "asc")

    query = ServiceItem.not_deleted()

    if q:
        search_term = f"%{q}%"
        query = query.filter(
            db.or_(
                ServiceItem.name.ilike(search_term),
                ServiceItem.serial_number.ilike(search_term),
                ServiceItem.brand.ilike(search_term),
                ServiceItem.model.ilike(search_term),
            )
        )

    # Validate sort against allowlist to prevent attribute injection
    if sort not in SORTABLE_FIELDS:
        sort = "name"
    sort_column = getattr(ServiceItem, sort)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    pagination = query.paginate(page=page, per_page=25, error_out=False)

    return render_template(
        "items/list.html",
        items=pagination.items,
        pagination=pagination,
        q=q,
        sort=sort,
        order=order,
    )


@items_bp.route("/lookup")
@login_required
def lookup():
    """Serial number lookup page."""
    serial = request.args.get("serial", "")
    item = None

    if serial:
        item = ServiceItem.not_deleted().filter_by(serial_number=serial).first()

    return render_template("items/lookup.html", serial=serial, item=item)


@items_bp.route("/<int:id>")
@login_required
def detail(id):
    """Display a service item detail page."""
    item = db.session.get(ServiceItem, id)
    if item is None or item.is_deleted:
        abort(404)
    return render_template("items/detail.html", item=item)


@items_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_accepted("admin", "technician")
def create():
    """Show new item form (GET) or create an item (POST)."""
    form = ServiceItemForm()
    drysuit_form = DrysuitDetailsForm(prefix="drysuit")

    # Pre-populate customer_id from query string if provided
    customer_id = request.args.get("customer_id", type=int)
    if request.method == "GET" and customer_id:
        form.customer_id.data = str(customer_id)

    if form.validate_on_submit():
        item = ServiceItem(
            serial_number=form.serial_number.data or None,
            name=form.name.data,
            item_category=form.item_category.data,
            serviceability=form.serviceability.data,
            serviceability_notes=form.serviceability_notes.data,
            brand=form.brand.data,
            model=form.model.data,
            year_manufactured=form.year_manufactured.data,
            notes=form.notes.data,
            customer_id=form.customer_id.data or None,
            created_by=current_user.id,
        )
        db.session.add(item)
        try:
            db.session.flush()

            # Create drysuit details if category is Drysuit
            if form.item_category.data == "Drysuit":
                drysuit = DrysuitDetails(service_item_id=item.id)
                _populate_drysuit_details(drysuit, drysuit_form)
                db.session.add(drysuit)

            db.session.commit()
            try:
                audit_service.log_action(
                    action="create",
                    entity_type="service_item",
                    entity_id=item.id,
                    user_id=current_user.id,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                )
            except Exception:
                pass
            flash("Service item created successfully.", "success")
            return redirect(url_for("items.detail", id=item.id))
        except IntegrityError:
            db.session.rollback()
            flash("A service item with that serial number already exists.", "error")

    return render_template(
        "items/form.html",
        form=form,
        drysuit_form=drysuit_form,
        is_edit=False,
    )


@items_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@roles_accepted("admin", "technician")
def edit(id):
    """Show edit item form (GET) or update the item (POST)."""
    item = db.session.get(ServiceItem, id)
    if item is None or item.is_deleted:
        abort(404)

    form = ServiceItemForm(obj=item)
    drysuit_form = DrysuitDetailsForm(
        prefix="drysuit", obj=item.drysuit_details
    )

    if form.validate_on_submit():
        form.populate_obj(item)
        # Ensure empty serial number is stored as None (unique constraint)
        if not item.serial_number:
            item.serial_number = None

        # Handle drysuit details
        if form.item_category.data == "Drysuit":
            if item.drysuit_details is None:
                drysuit = DrysuitDetails(service_item_id=item.id)
                db.session.add(drysuit)
                item.drysuit_details = drysuit
            _populate_drysuit_details(item.drysuit_details, drysuit_form)
        else:
            # Remove drysuit details if category changed away from Drysuit
            if item.drysuit_details is not None:
                db.session.delete(item.drysuit_details)

        try:
            db.session.commit()
            try:
                audit_service.log_action(
                    action="update",
                    entity_type="service_item",
                    entity_id=item.id,
                    user_id=current_user.id,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                )
            except Exception:
                pass
            flash("Service item updated successfully.", "success")
            return redirect(url_for("items.detail", id=item.id))
        except IntegrityError:
            db.session.rollback()
            flash("A service item with that serial number already exists.", "error")

    return render_template(
        "items/form.html",
        form=form,
        drysuit_form=drysuit_form,
        item=item,
        is_edit=True,
    )


@items_bp.route("/<int:id>/delete", methods=["POST"])
@login_required
@roles_accepted("admin")
def delete(id):
    """Soft-delete a service item (admin only)."""
    item = db.session.get(ServiceItem, id)
    if item is None or item.is_deleted:
        abort(404)

    item.soft_delete()
    db.session.commit()
    try:
        audit_service.log_action(
            action="delete",
            entity_type="service_item",
            entity_id=item.id,
            user_id=current_user.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
        )
    except Exception:
        pass
    flash("Service item deleted.", "success")
    return redirect(url_for("items.list_items"))


def _populate_drysuit_details(drysuit, form):
    """Copy drysuit form data onto a DrysuitDetails instance."""
    drysuit_fields = [
        "size", "material_type", "material_thickness", "color",
        "suit_entry_type", "neck_seal_type", "neck_seal_system",
        "wrist_seal_type", "wrist_seal_system", "zipper_type",
        "zipper_length", "zipper_orientation", "inflate_valve_brand",
        "inflate_valve_model", "inflate_valve_position", "dump_valve_brand",
        "dump_valve_model", "dump_valve_type", "boot_type", "boot_size",
    ]
    for field_name in drysuit_fields:
        field = getattr(form, field_name, None)
        if field is not None:
            setattr(drysuit, field_name, field.data or None)
