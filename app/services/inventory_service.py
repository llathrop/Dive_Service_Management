"""Inventory service layer — business logic for inventory item management.

Provides module-level functions for CRUD operations, stock adjustments,
low-stock detection, and category listing for inventory items.
"""

from flask import abort
from sqlalchemy import or_

from app.extensions import db
from app.models.inventory import InventoryItem


def get_inventory_items(
    page=1,
    per_page=25,
    search=None,
    category=None,
    low_stock_only=False,
    is_active=None,
    sort="name",
    order="asc",
):
    """Return paginated, filtered inventory listing.

    Args:
        page: Page number (1-indexed).
        per_page: Number of results per page.
        search: Optional search string (matches name, SKU, manufacturer).
        category: Optional category filter.
        low_stock_only: If True, return only items at or below reorder level.
        is_active: If provided, filter by active/inactive status.
        sort: Column name to sort by.
        order: Sort direction, 'asc' or 'desc'.

    Returns:
        A SQLAlchemy pagination object.
    """
    query = InventoryItem.not_deleted()

    # Apply search filter
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                InventoryItem.name.ilike(pattern),
                InventoryItem.sku.ilike(pattern),
                InventoryItem.manufacturer.ilike(pattern),
            )
        )

    # Apply category filter
    if category:
        query = query.filter(InventoryItem.category == category)

    # Apply low stock filter
    if low_stock_only:
        query = query.filter(
            InventoryItem.reorder_level > 0,
            InventoryItem.quantity_in_stock <= InventoryItem.reorder_level,
        )

    # Apply active status filter
    if is_active is not None:
        query = query.filter(InventoryItem.is_active == is_active)

    # Apply sorting
    sort_column = getattr(InventoryItem, sort, InventoryItem.name)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    return db.paginate(query, page=page, per_page=per_page)


def get_inventory_item(item_id):
    """Return a single inventory item by ID or raise 404.

    Args:
        item_id: The primary key of the inventory item.

    Returns:
        An InventoryItem instance.

    Raises:
        404 HTTPException if the item does not exist.
    """
    item = db.session.get(InventoryItem, item_id)
    if item is None or item.is_deleted:
        abort(404)
    return item


def create_inventory_item(data, created_by=None):
    """Create a new inventory item from a data dict.

    Args:
        data: Dictionary of inventory item fields.
        created_by: Optional user ID of the creator.

    Returns:
        The newly created InventoryItem instance.
    """
    item = InventoryItem(
        sku=data.get("sku"),
        name=data["name"],
        description=data.get("description"),
        category=data["category"],
        subcategory=data.get("subcategory"),
        manufacturer=data.get("manufacturer"),
        manufacturer_part_number=data.get("manufacturer_part_number"),
        purchase_cost=data.get("purchase_cost"),
        resale_price=data.get("resale_price"),
        markup_percent=data.get("markup_percent"),
        quantity_in_stock=data.get("quantity_in_stock", 0),
        reorder_level=data.get("reorder_level", 0),
        reorder_quantity=data.get("reorder_quantity"),
        unit_of_measure=data.get("unit_of_measure", "each"),
        storage_location=data.get("storage_location"),
        is_active=data.get("is_active", True),
        is_for_resale=data.get("is_for_resale", False),
        preferred_supplier=data.get("preferred_supplier"),
        supplier_url=data.get("supplier_url"),
        minimum_order_quantity=data.get("minimum_order_quantity"),
        supplier_lead_time_days=data.get("supplier_lead_time_days"),
        expiration_date=data.get("expiration_date"),
        notes=data.get("notes"),
        created_by=created_by,
    )
    db.session.add(item)
    db.session.commit()
    return item


def update_inventory_item(item_id, data):
    """Update an existing inventory item from a data dict.

    Args:
        item_id: The primary key of the item to update.
        data: Dictionary of fields to update.

    Returns:
        The updated InventoryItem instance.

    Raises:
        404 HTTPException if the item does not exist.
    """
    item = get_inventory_item(item_id)

    for field in (
        "sku",
        "name",
        "description",
        "category",
        "subcategory",
        "manufacturer",
        "manufacturer_part_number",
        "purchase_cost",
        "resale_price",
        "markup_percent",
        "quantity_in_stock",
        "reorder_level",
        "reorder_quantity",
        "unit_of_measure",
        "storage_location",
        "is_active",
        "is_for_resale",
        "preferred_supplier",
        "supplier_url",
        "minimum_order_quantity",
        "supplier_lead_time_days",
        "expiration_date",
        "notes",
    ):
        if field in data:
            setattr(item, field, data[field])

    db.session.commit()
    return item


def delete_inventory_item(item_id):
    """Soft-delete an inventory item.

    Args:
        item_id: The primary key of the item to delete.

    Returns:
        The soft-deleted InventoryItem instance.

    Raises:
        404 HTTPException if the item does not exist.
    """
    item = get_inventory_item(item_id)
    item.soft_delete()
    db.session.commit()
    return item


def adjust_stock(item_id, adjustment, reason, adjusted_by=None):
    """Adjust stock level for an inventory item.

    The adjustment can be positive (add stock) or negative (remove stock).
    Raises ValueError if the resulting stock would be negative.

    Args:
        item_id: The primary key of the item.
        adjustment: Integer amount to adjust (positive or negative).
        reason: A string describing why the adjustment was made.
        adjusted_by: Optional user ID of who performed the adjustment.

    Returns:
        The updated InventoryItem instance.

    Raises:
        ValueError: If the adjustment would result in negative stock.
        404 HTTPException: If the item does not exist.
    """
    item = get_inventory_item(item_id)
    new_quantity = item.quantity_in_stock + adjustment

    if new_quantity < 0:
        raise ValueError(
            f"Stock adjustment would result in negative stock "
            f"({item.quantity_in_stock} + {adjustment} = {new_quantity})."
        )

    item.quantity_in_stock = new_quantity
    db.session.commit()
    return item


def get_low_stock_items():
    """Return all active items where quantity_in_stock <= reorder_level.

    Only includes items where reorder_level > 0 (i.e. reorder tracking
    has been configured).

    Returns:
        A list of InventoryItem instances that are low on stock.
    """
    return (
        InventoryItem.not_deleted()
        .filter(
            InventoryItem.is_active.is_(True),
            InventoryItem.reorder_level > 0,
            InventoryItem.quantity_in_stock <= InventoryItem.reorder_level,
        )
        .all()
    )


def get_categories():
    """Return a distinct list of categories for filter dropdowns.

    Returns:
        A sorted list of category name strings.
    """
    rows = (
        db.session.query(InventoryItem.category)
        .filter(InventoryItem.is_deleted.is_(False))
        .distinct()
        .order_by(InventoryItem.category)
        .all()
    )
    return [row[0] for row in rows]
