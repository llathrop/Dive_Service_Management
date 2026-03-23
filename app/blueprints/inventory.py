"""Inventory blueprint.

Provides routes for managing shop inventory items (parts, consumables,
resale stock).  Supports listing, creation, editing, soft-deletion,
stock adjustments, and a low-stock filtered view.  All routes require
authentication.  Write operations require 'admin' or 'technician' role.
"""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_security import current_user, login_required, roles_accepted
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms.inventory import InventoryItemForm, InventorySearchForm, StockAdjustmentForm
from app.services import audit_service, inventory_service, saved_search_service

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")

# Columns that the list view is allowed to sort by.
SORTABLE_FIELDS = {
    "name", "sku", "category", "subcategory", "manufacturer",
    "quantity_in_stock", "reorder_level", "purchase_cost",
    "resale_price", "is_active", "created_at",
}


@inventory_bp.route("/")
@login_required
def list_items():
    """List inventory items with pagination, search, and filtering."""
    # Apply default saved search when no filter params are provided
    filter_keys = ["q", "category", "low_stock_only", "is_active", "sort", "order"]
    if not any(request.args.get(k) for k in filter_keys):
        default_search = saved_search_service.get_default_search(
            user_id=current_user.id, search_type="inventory"
        )
        if default_search:
            filters = default_search.filters
            from werkzeug.datastructures import ImmutableMultiDict
            args = ImmutableMultiDict(filters)
            form = InventorySearchForm(args)
            page = int(filters.get("page", 1))
            sort = filters.get("sort", "name")
            order = filters.get("order", "asc")
        else:
            form = InventorySearchForm(request.args)
            page = request.args.get("page", 1, type=int)
            sort = request.args.get("sort", "name")
            order = request.args.get("order", "asc")
    else:
        form = InventorySearchForm(request.args)
        page = request.args.get("page", 1, type=int)
        sort = request.args.get("sort", "name")
        order = request.args.get("order", "asc")

    # Populate category choices dynamically
    categories = inventory_service.get_categories()
    form.category.choices = [("", "All")] + [(c, c) for c in categories]

    # Validate sort against allowlist to prevent attribute injection
    if sort not in SORTABLE_FIELDS:
        sort = "name"

    # Map is_active form value to boolean or None
    is_active = None
    if form.is_active.data == "1":
        is_active = True
    elif form.is_active.data == "0":
        is_active = False

    pagination = inventory_service.get_inventory_items(
        page=page,
        per_page=25,
        search=form.q.data,
        category=form.category.data,
        low_stock_only=form.low_stock_only.data,
        is_active=is_active,
        sort=sort,
        order=order,
    )

    return render_template(
        "inventory/list.html",
        items=pagination.items,
        pagination=pagination,
        form=form,
        sort=sort,
        order=order,
    )


@inventory_bp.route("/low-stock")
@login_required
def low_stock():
    """Display a filtered view of low-stock inventory items."""
    page = request.args.get("page", 1, type=int)

    pagination = inventory_service.get_inventory_items(
        page=page,
        per_page=25,
        low_stock_only=True,
        is_active=True,
        sort="quantity_in_stock",
        order="asc",
    )

    return render_template(
        "inventory/low_stock.html",
        items=pagination.items,
        pagination=pagination,
    )


@inventory_bp.route("/<int:id>")
@login_required
def detail(id):
    """Display inventory item detail with stock adjustment form."""
    item = inventory_service.get_inventory_item(id)
    adjustment_form = StockAdjustmentForm()
    return render_template(
        "inventory/detail.html", item=item, adjustment_form=adjustment_form
    )


@inventory_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_accepted("admin", "technician")
def create():
    """Show new inventory item form (GET) or create an item (POST)."""
    form = InventoryItemForm()

    if form.validate_on_submit():
        data = {
            "sku": form.sku.data or None,
            "name": form.name.data,
            "description": form.description.data,
            "category": form.category.data,
            "subcategory": form.subcategory.data,
            "manufacturer": form.manufacturer.data,
            "manufacturer_part_number": form.manufacturer_part_number.data,
            "purchase_cost": form.purchase_cost.data,
            "resale_price": form.resale_price.data,
            "markup_percent": form.markup_percent.data,
            "quantity_in_stock": form.quantity_in_stock.data or 0,
            "reorder_level": form.reorder_level.data or 0,
            "reorder_quantity": form.reorder_quantity.data,
            "unit_of_measure": form.unit_of_measure.data,
            "storage_location": form.storage_location.data,
            "is_active": form.is_active.data,
            "is_for_resale": form.is_for_resale.data,
            "preferred_supplier": form.preferred_supplier.data,
            "supplier_url": form.supplier_url.data,
            "minimum_order_quantity": form.minimum_order_quantity.data,
            "supplier_lead_time_days": form.supplier_lead_time_days.data,
            "expiration_date": form.expiration_date.data,
            "notes": form.notes.data,
        }
        try:
            item = inventory_service.create_inventory_item(
                data, created_by=current_user.id
            )
            try:
                audit_service.log_action(
                    action="create",
                    entity_type="inventory_item",
                    entity_id=item.id,
                    user_id=current_user.id,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                )
            except Exception:
                pass
            flash("Inventory item created successfully.", "success")
            return redirect(url_for("inventory.detail", id=item.id))
        except IntegrityError:
            db.session.rollback()
            flash("An inventory item with that SKU already exists.", "error")

    return render_template("inventory/form.html", form=form, is_edit=False)


@inventory_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@roles_accepted("admin", "technician")
def edit(id):
    """Show edit inventory item form (GET) or update the item (POST)."""
    item = inventory_service.get_inventory_item(id)

    form = InventoryItemForm(obj=item)

    if form.validate_on_submit():
        data = {
            "sku": form.sku.data or None,
            "name": form.name.data,
            "description": form.description.data,
            "category": form.category.data,
            "subcategory": form.subcategory.data,
            "manufacturer": form.manufacturer.data,
            "manufacturer_part_number": form.manufacturer_part_number.data,
            "purchase_cost": form.purchase_cost.data,
            "resale_price": form.resale_price.data,
            "markup_percent": form.markup_percent.data,
            "quantity_in_stock": form.quantity_in_stock.data or 0,
            "reorder_level": form.reorder_level.data or 0,
            "reorder_quantity": form.reorder_quantity.data,
            "unit_of_measure": form.unit_of_measure.data,
            "storage_location": form.storage_location.data,
            "is_active": form.is_active.data,
            "is_for_resale": form.is_for_resale.data,
            "preferred_supplier": form.preferred_supplier.data,
            "supplier_url": form.supplier_url.data,
            "minimum_order_quantity": form.minimum_order_quantity.data,
            "supplier_lead_time_days": form.supplier_lead_time_days.data,
            "expiration_date": form.expiration_date.data,
            "notes": form.notes.data,
        }
        try:
            item = inventory_service.update_inventory_item(id, data)
            try:
                audit_service.log_action(
                    action="update",
                    entity_type="inventory_item",
                    entity_id=item.id,
                    user_id=current_user.id,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                )
            except Exception:
                pass
            flash("Inventory item updated successfully.", "success")
            return redirect(url_for("inventory.detail", id=item.id))
        except IntegrityError:
            db.session.rollback()
            flash("An inventory item with that SKU already exists.", "error")

    return render_template(
        "inventory/form.html", form=form, item=item, is_edit=True
    )


@inventory_bp.route("/<int:id>/delete", methods=["POST"])
@login_required
@roles_accepted("admin")
def delete(id):
    """Soft-delete an inventory item (admin only)."""
    item = inventory_service.delete_inventory_item(id)
    try:
        audit_service.log_action(
            action="delete",
            entity_type="inventory_item",
            entity_id=item.id,
            user_id=current_user.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
        )
    except Exception:
        pass
    flash("Inventory item deleted.", "success")
    return redirect(url_for("inventory.list_items"))


@inventory_bp.route("/<int:id>/adjust", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def adjust_stock(id):
    """Adjust the stock level of an inventory item."""
    item = inventory_service.get_inventory_item(id)

    form = StockAdjustmentForm()

    if form.validate_on_submit():
        old_qty = item.quantity_in_stock
        try:
            item = inventory_service.adjust_stock(
                id, form.adjustment.data, reason=None, adjusted_by=current_user.id
            )
            try:
                audit_service.log_action(
                    action="update",
                    entity_type="inventory_item",
                    entity_id=item.id,
                    user_id=current_user.id,
                    field_name="quantity_in_stock",
                    old_value=str(old_qty),
                    new_value=str(item.quantity_in_stock),
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                )
            except Exception:
                pass
            flash(
                f"Stock adjusted by {form.adjustment.data:+}. "
                f"New quantity: {item.quantity_in_stock}.",
                "success",
            )
        except ValueError:
            flash(
                f"Cannot adjust by {form.adjustment.data:+}: "
                f"would result in negative stock.",
                "danger",
            )
    else:
        flash("Invalid stock adjustment.", "danger")

    return redirect(url_for("inventory.detail", id=id))


@inventory_bp.route("/quick-create", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def quick_create():
    """Create a new inventory item inline and return JSON with id + display_text.

    Accepts form fields: name (required), sku (optional), category (optional),
    unit_cost (optional), quantity_in_stock (optional, default 0),
    reorder_level (optional, default 0).  Returns JSON so the frontend can add
    the new item to the select dropdown without a page reload.
    """
    name = request.form.get("name", "").strip()
    sku = request.form.get("sku", "").strip() or None
    category = request.form.get("category", "").strip() or "General"
    unit_cost_str = request.form.get("unit_cost", "").strip()
    qty_str = request.form.get("quantity_in_stock", "").strip()
    reorder_str = request.form.get("reorder_level", "").strip()

    if not name:
        return jsonify({"error": "Item name is required."}), 400

    if len(name) > 255:
        return jsonify({"error": "Name exceeds 255 characters."}), 400

    unit_cost = None
    if unit_cost_str:
        try:
            unit_cost = float(unit_cost_str)
        except (ValueError, TypeError):
            return jsonify({"error": "Unit cost must be a valid number."}), 400

    quantity_in_stock = 0
    if qty_str:
        try:
            quantity_in_stock = float(qty_str)
        except (ValueError, TypeError):
            return jsonify({"error": "Quantity must be a valid number."}), 400

    reorder_level = 0
    if reorder_str:
        try:
            reorder_level = float(reorder_str)
        except (ValueError, TypeError):
            return jsonify({"error": "Reorder level must be a valid number."}), 400

    # Validate non-negative values
    if unit_cost is not None and unit_cost < 0:
        return jsonify({"error": "Unit cost must be zero or positive."}), 400
    if quantity_in_stock < 0:
        return jsonify({"error": "Quantity must be zero or positive."}), 400
    if reorder_level < 0:
        return jsonify({"error": "Reorder level must be zero or positive."}), 400

    data = {
        "name": name,
        "sku": sku,
        "category": category,
        "purchase_cost": unit_cost,
        "quantity_in_stock": quantity_in_stock,
        "reorder_level": reorder_level,
    }

    try:
        item = inventory_service.create_inventory_item(
            data, created_by=current_user.id
        )
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "An inventory item with that SKU already exists."}), 409

    try:
        audit_service.log_action(
            action="create",
            entity_type="inventory_item",
            entity_id=item.id,
            user_id=current_user.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
        )
    except Exception:
        pass

    display_text = f"{item.name} (SKU: {item.sku})" if item.sku else item.name
    return jsonify({"id": item.id, "display_text": display_text}), 201
