"""Inventory blueprint.

Provides routes for managing shop inventory items (parts, consumables,
resale stock).  Supports listing, creation, editing, soft-deletion,
stock adjustments, and a low-stock filtered view.  All routes require
authentication.  Write operations require 'admin' or 'technician' role.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_security import current_user, login_required, roles_accepted
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms.inventory import InventoryItemForm, InventorySearchForm, StockAdjustmentForm
from app.models.inventory import InventoryItem

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
    form = InventorySearchForm(request.args)
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "name")
    order = request.args.get("order", "asc")

    query = InventoryItem.not_deleted()

    # Populate category choices dynamically
    categories = (
        db.session.query(InventoryItem.category)
        .filter_by(is_deleted=False)
        .distinct()
        .order_by(InventoryItem.category)
        .all()
    )
    form.category.choices = [("", "All")] + [
        (c[0], c[0]) for c in categories
    ]

    # Apply search filter
    if form.q.data:
        search_term = f"%{form.q.data}%"
        query = query.filter(
            db.or_(
                InventoryItem.name.ilike(search_term),
                InventoryItem.sku.ilike(search_term),
                InventoryItem.manufacturer.ilike(search_term),
                InventoryItem.description.ilike(search_term),
            )
        )

    # Apply category filter
    if form.category.data:
        query = query.filter_by(category=form.category.data)

    # Apply low stock filter
    if form.low_stock_only.data:
        query = query.filter(
            InventoryItem.reorder_level > 0,
            InventoryItem.quantity_in_stock <= InventoryItem.reorder_level,
        )

    # Apply active status filter
    if form.is_active.data == "1":
        query = query.filter_by(is_active=True)
    elif form.is_active.data == "0":
        query = query.filter_by(is_active=False)

    # Apply sorting -- validate against allowlist to prevent attribute injection
    if sort not in SORTABLE_FIELDS:
        sort = "name"
    sort_column = getattr(InventoryItem, sort)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    pagination = query.paginate(page=page, per_page=25, error_out=False)

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

    query = InventoryItem.not_deleted().filter(
        InventoryItem.is_active == True,  # noqa: E712
        InventoryItem.reorder_level > 0,
        InventoryItem.quantity_in_stock <= InventoryItem.reorder_level,
    )
    query = query.order_by(InventoryItem.quantity_in_stock.asc())

    pagination = query.paginate(page=page, per_page=25, error_out=False)

    return render_template(
        "inventory/low_stock.html",
        items=pagination.items,
        pagination=pagination,
    )


@inventory_bp.route("/<int:id>")
@login_required
def detail(id):
    """Display inventory item detail with stock adjustment form."""
    item = db.session.get(InventoryItem, id)
    if item is None or item.is_deleted:
        abort(404)
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
        item = InventoryItem(
            sku=form.sku.data or None,
            name=form.name.data,
            description=form.description.data,
            category=form.category.data,
            subcategory=form.subcategory.data,
            manufacturer=form.manufacturer.data,
            manufacturer_part_number=form.manufacturer_part_number.data,
            purchase_cost=form.purchase_cost.data,
            resale_price=form.resale_price.data,
            markup_percent=form.markup_percent.data,
            quantity_in_stock=form.quantity_in_stock.data or 0,
            reorder_level=form.reorder_level.data or 0,
            reorder_quantity=form.reorder_quantity.data,
            unit_of_measure=form.unit_of_measure.data,
            storage_location=form.storage_location.data,
            is_active=form.is_active.data,
            is_for_resale=form.is_for_resale.data,
            preferred_supplier=form.preferred_supplier.data,
            supplier_url=form.supplier_url.data,
            minimum_order_quantity=form.minimum_order_quantity.data,
            supplier_lead_time_days=form.supplier_lead_time_days.data,
            expiration_date=form.expiration_date.data,
            notes=form.notes.data,
            created_by=current_user.id,
        )
        db.session.add(item)
        try:
            db.session.commit()
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
    item = db.session.get(InventoryItem, id)
    if item is None or item.is_deleted:
        abort(404)

    form = InventoryItemForm(obj=item)

    if form.validate_on_submit():
        form.populate_obj(item)
        # Ensure empty SKU is stored as None (unique constraint)
        if not item.sku:
            item.sku = None
        try:
            db.session.commit()
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
    item = db.session.get(InventoryItem, id)
    if item is None or item.is_deleted:
        abort(404)

    item.soft_delete()
    db.session.commit()
    flash("Inventory item deleted.", "success")
    return redirect(url_for("inventory.list_items"))


@inventory_bp.route("/<int:id>/adjust", methods=["POST"])
@login_required
@roles_accepted("admin", "technician")
def adjust_stock(id):
    """Adjust the stock level of an inventory item."""
    item = db.session.get(InventoryItem, id)
    if item is None or item.is_deleted:
        abort(404)

    form = StockAdjustmentForm()

    if form.validate_on_submit():
        new_qty = item.quantity_in_stock + form.adjustment.data
        if new_qty < 0:
            flash(
                f"Cannot adjust by {form.adjustment.data:+}: "
                f"would result in negative stock ({new_qty}).",
                "danger",
            )
        else:
            item.quantity_in_stock = new_qty
            db.session.commit()
            flash(
                f"Stock adjusted by {form.adjustment.data:+}. "
                f"New quantity: {item.quantity_in_stock}.",
                "success",
            )
    else:
        flash("Invalid stock adjustment.", "danger")

    return redirect(url_for("inventory.detail", id=item.id))
