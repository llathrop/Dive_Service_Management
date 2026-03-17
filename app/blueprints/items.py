"""Service Items blueprint.

Provides routes for listing, creating, viewing, editing, and soft-deleting
service items (customer-owned dive equipment).  Supports drysuit-specific
detail fields via the DrysuitDetails model.  All routes require
authentication.  Write operations require the 'admin' or 'technician' role.
"""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_security import current_user, login_required, roles_accepted
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms.item import DrysuitDetailsForm, ServiceItemForm
from app.services import audit_service, item_service

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

    # Validate sort against allowlist to prevent attribute injection
    if sort not in SORTABLE_FIELDS:
        sort = "name"

    pagination = item_service.get_items(
        page=page,
        per_page=25,
        search=q,
        sort=sort,
        order=order,
    )

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
    item = item_service.lookup_by_serial(serial) if serial else None

    return render_template("items/lookup.html", serial=serial, item=item)


@items_bp.route("/<int:id>")
@login_required
def detail(id):
    """Display a service item detail page."""
    item = item_service.get_item(id)
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
        data = {
            "serial_number": form.serial_number.data,
            "name": form.name.data,
            "item_category": form.item_category.data,
            "serviceability": form.serviceability.data,
            "serviceability_notes": form.serviceability_notes.data,
            "brand": form.brand.data,
            "model": form.model.data,
            "year_manufactured": form.year_manufactured.data,
            "notes": form.notes.data,
            "customer_id": form.customer_id.data,
        }
        drysuit_data = _extract_drysuit_data(drysuit_form)

        try:
            item = item_service.create_item(
                data, drysuit_data=drysuit_data, created_by=current_user.id
            )
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
    item = item_service.get_item(id)

    form = ServiceItemForm(obj=item)
    drysuit_form = DrysuitDetailsForm(
        prefix="drysuit", obj=item.drysuit_details
    )

    if form.validate_on_submit():
        data = {
            "serial_number": form.serial_number.data,
            "name": form.name.data,
            "item_category": form.item_category.data,
            "serviceability": form.serviceability.data,
            "serviceability_notes": form.serviceability_notes.data,
            "brand": form.brand.data,
            "model": form.model.data,
            "year_manufactured": form.year_manufactured.data,
            "notes": form.notes.data,
            "customer_id": form.customer_id.data,
        }
        drysuit_data = _extract_drysuit_data(drysuit_form)

        try:
            item_service.update_item(
                id, data, drysuit_data=drysuit_data
            )
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
    item = item_service.delete_item(id)
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


# Valid item categories for quick-create validation
VALID_CATEGORIES = {
    "Regulator", "BCD", "Drysuit", "Wetsuit", "Computer", "Tank", "Other",
}


@items_bp.route("/quick-create", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def quick_create():
    """Create a new service item inline and return JSON with id + display_text.

    Accepts form fields: name (required), serial_number, item_category,
    brand, model, customer_id.  Returns JSON so the frontend can add the
    new item to the select dropdown without a page reload.
    """
    name = request.form.get("name", "").strip()
    serial_number = request.form.get("serial_number", "").strip() or None
    item_category = request.form.get("item_category", "").strip() or None
    brand = request.form.get("brand", "").strip() or None
    model = request.form.get("model", "").strip() or None
    customer_id = request.form.get("customer_id", type=int) or None

    if not name:
        return jsonify({"error": "Item name is required."}), 400

    if item_category and item_category not in VALID_CATEGORIES:
        return jsonify({"error": "Invalid item category."}), 400

    data = {
        "name": name,
        "serial_number": serial_number,
        "item_category": item_category,
        "brand": brand,
        "model": model,
        "customer_id": customer_id,
    }

    try:
        item = item_service.create_item(data, created_by=current_user.id)
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "A service item with that serial number already exists."}), 409

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

    display_text = f"{item.name} ({item.serial_number})" if item.serial_number else item.name
    return jsonify({"id": item.id, "display_text": display_text}), 201


def _extract_drysuit_data(drysuit_form):
    """Extract drysuit field values from the form into a dict."""
    from app.services.item_service import DRYSUIT_FIELDS

    data = {}
    for field_name in DRYSUIT_FIELDS:
        field = getattr(drysuit_form, field_name, None)
        if field is not None:
            data[field_name] = field.data
    return data
