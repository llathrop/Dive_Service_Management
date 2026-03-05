"""Price list service layer — business logic for price list management.

Provides module-level functions for managing price list categories, items,
and linking inventory parts to price list items.
"""

from flask import abort
from sqlalchemy import or_

from app.extensions import db
from app.models.price_list import (
    PriceListCategory,
    PriceListItem,
    PriceListItemPart,
)


# ---------------------------------------------------------------------------
# Category operations
# ---------------------------------------------------------------------------


def get_categories(active_only=True):
    """Return all categories ordered by sort_order.

    Args:
        active_only: If True, only return active categories.

    Returns:
        A list of PriceListCategory instances.
    """
    query = PriceListCategory.query.order_by(PriceListCategory.sort_order)
    if active_only:
        query = query.filter(PriceListCategory.is_active.is_(True))
    return query.all()


def get_category(category_id):
    """Return a single category by ID or raise 404.

    Args:
        category_id: The primary key of the category.

    Returns:
        A PriceListCategory instance.

    Raises:
        404 HTTPException if the category does not exist.
    """
    category = db.session.get(PriceListCategory, category_id)
    if category is None:
        abort(404)
    return category


def create_category(data):
    """Create a price list category from a data dict.

    Args:
        data: Dictionary of category fields.

    Returns:
        The newly created PriceListCategory instance.
    """
    category = PriceListCategory(
        name=data["name"],
        description=data.get("description"),
        sort_order=data.get("sort_order", 0),
        is_active=data.get("is_active", True),
    )
    db.session.add(category)
    db.session.commit()
    return category


def update_category(category_id, data):
    """Update a price list category.

    Args:
        category_id: The primary key of the category to update.
        data: Dictionary of fields to update.

    Returns:
        The updated PriceListCategory instance.

    Raises:
        404 HTTPException if the category does not exist.
    """
    category = get_category(category_id)

    for field in ("name", "description", "sort_order", "is_active"):
        if field in data:
            setattr(category, field, data[field])

    db.session.commit()
    return category


# ---------------------------------------------------------------------------
# Price list item operations
# ---------------------------------------------------------------------------


def get_price_list_items(category_id=None, active_only=True, search=None):
    """Return price list items, optionally filtered.

    Args:
        category_id: Optional category ID to filter by.
        active_only: If True, only return active items.
        search: Optional search text to match against name, code, or
            description.

    Returns:
        A list of PriceListItem instances.
    """
    query = PriceListItem.query

    if category_id is not None:
        query = query.filter(PriceListItem.category_id == category_id)

    if active_only:
        query = query.filter(PriceListItem.is_active.is_(True))

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                PriceListItem.name.ilike(pattern),
                PriceListItem.code.ilike(pattern),
                PriceListItem.description.ilike(pattern),
            )
        )

    return query.order_by(PriceListItem.sort_order, PriceListItem.name).all()


def get_price_list_item(item_id):
    """Return a single price list item by ID or raise 404.

    Args:
        item_id: The primary key of the price list item.

    Returns:
        A PriceListItem instance.

    Raises:
        404 HTTPException if the item does not exist.
    """
    item = db.session.get(PriceListItem, item_id)
    if item is None:
        abort(404)
    return item


def create_price_list_item(data, updated_by=None):
    """Create a price list item from a data dict.

    Args:
        data: Dictionary of price list item fields.
        updated_by: Optional user ID of who created this item.

    Returns:
        The newly created PriceListItem instance.
    """
    item = PriceListItem(
        category_id=data["category_id"],
        code=data.get("code"),
        name=data["name"],
        description=data.get("description"),
        price=data["price"],
        cost=data.get("cost"),
        price_tier=data.get("price_tier"),
        is_per_unit=data.get("is_per_unit", True),
        default_quantity=data.get("default_quantity", 1),
        unit_label=data.get("unit_label", "each"),
        auto_deduct_parts=data.get("auto_deduct_parts", False),
        is_taxable=data.get("is_taxable", True),
        sort_order=data.get("sort_order", 0),
        is_active=data.get("is_active", True),
        internal_notes=data.get("internal_notes"),
        updated_by=updated_by,
    )
    db.session.add(item)
    db.session.commit()
    return item


def update_price_list_item(item_id, data, updated_by=None):
    """Update a price list item from a data dict.

    Args:
        item_id: The primary key of the item to update.
        data: Dictionary of fields to update.
        updated_by: Optional user ID of who made the update.

    Returns:
        The updated PriceListItem instance.

    Raises:
        404 HTTPException if the item does not exist.
    """
    item = get_price_list_item(item_id)

    for field in (
        "category_id",
        "code",
        "name",
        "description",
        "price",
        "cost",
        "price_tier",
        "is_per_unit",
        "default_quantity",
        "unit_label",
        "auto_deduct_parts",
        "is_taxable",
        "sort_order",
        "is_active",
        "internal_notes",
    ):
        if field in data:
            setattr(item, field, data[field])

    if updated_by is not None:
        item.updated_by = updated_by

    db.session.commit()
    return item


def duplicate_price_list_item(item_id):
    """Create a copy of an existing price list item.

    The copy has ' (Copy)' appended to the name and the code is cleared
    to avoid uniqueness conflicts.

    Args:
        item_id: The primary key of the item to duplicate.

    Returns:
        The newly created duplicate PriceListItem instance.

    Raises:
        404 HTTPException if the source item does not exist.
    """
    source = get_price_list_item(item_id)

    duplicate = PriceListItem(
        category_id=source.category_id,
        code=None,  # Clear code to avoid unique constraint violation
        name=f"{source.name} (Copy)",
        description=source.description,
        price=source.price,
        cost=source.cost,
        price_tier=source.price_tier,
        is_per_unit=source.is_per_unit,
        default_quantity=source.default_quantity,
        unit_label=source.unit_label,
        auto_deduct_parts=source.auto_deduct_parts,
        is_taxable=source.is_taxable,
        sort_order=source.sort_order,
        is_active=source.is_active,
        internal_notes=source.internal_notes,
    )
    db.session.add(duplicate)
    db.session.commit()
    return duplicate


# ---------------------------------------------------------------------------
# Part linking operations
# ---------------------------------------------------------------------------


def link_part(item_id, inventory_item_id, quantity=1, notes=None):
    """Link an inventory item to a price list item.

    Args:
        item_id: The price list item ID.
        inventory_item_id: The inventory item ID to link.
        quantity: The quantity of inventory item needed (default 1).
        notes: Optional notes about the link.

    Returns:
        The created PriceListItemPart instance.
    """
    link = PriceListItemPart(
        price_list_item_id=item_id,
        inventory_item_id=inventory_item_id,
        quantity=quantity,
        notes=notes,
    )
    db.session.add(link)
    db.session.commit()
    return link


def unlink_part(part_link_id):
    """Remove a PriceListItemPart link.

    Args:
        part_link_id: The primary key of the link to remove.

    Raises:
        404 HTTPException if the link does not exist.
    """
    link = db.session.get(PriceListItemPart, part_link_id)
    if link is None:
        abort(404)
    db.session.delete(link)
    db.session.commit()
