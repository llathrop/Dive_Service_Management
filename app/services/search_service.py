"""Search service layer — global search across multiple entity types.

Provides module-level functions for searching customers, service items,
and inventory items using LIKE queries (SQLite compatible).
"""

from sqlalchemy import or_

from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.service_item import ServiceItem


def global_search(query, limit=20):
    """Search across customers, service items, and inventory items.

    Returns a dict with results grouped by entity type.  Each result
    includes an 'id', a primary display field, and a 'type' field
    indicating the entity type.

    Args:
        query: The search text.
        limit: Maximum number of results per entity type.

    Returns:
        A dict with keys 'customers', 'service_items', and 'inventory_items',
        each containing a list of result dicts.
    """
    if not query:
        return {
            "customers": [],
            "service_items": [],
            "inventory_items": [],
        }

    return {
        "customers": search_customers(query, limit=limit),
        "service_items": search_service_items(query, limit=limit),
        "inventory_items": search_inventory_items(query, limit=limit),
    }


def search_customers(query, limit=10):
    """Search customers by name, business_name, email, or phone.

    Excludes soft-deleted customers.

    Args:
        query: The search text.
        limit: Maximum number of results to return.

    Returns:
        A list of dicts with 'id', 'display_name', 'email', and 'type' keys.
    """
    if not query:
        return []

    pattern = f"%{query}%"
    customers = (
        Customer.not_deleted()
        .filter(
            or_(
                Customer.first_name.ilike(pattern),
                Customer.last_name.ilike(pattern),
                Customer.business_name.ilike(pattern),
                Customer.email.ilike(pattern),
                Customer.phone_primary.ilike(pattern),
            )
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "id": c.id,
            "display_name": c.display_name,
            "email": c.email,
            "type": "customer",
        }
        for c in customers
    ]


def search_service_items(query, limit=10):
    """Search service items by name, serial number, brand, or model.

    Excludes soft-deleted items.

    Args:
        query: The search text.
        limit: Maximum number of results to return.

    Returns:
        A list of dicts with 'id', 'name', 'serial_number', and 'type' keys.
    """
    if not query:
        return []

    pattern = f"%{query}%"
    items = (
        ServiceItem.not_deleted()
        .filter(
            or_(
                ServiceItem.name.ilike(pattern),
                ServiceItem.serial_number.ilike(pattern),
                ServiceItem.brand.ilike(pattern),
                ServiceItem.model.ilike(pattern),
            )
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "id": item.id,
            "name": item.name,
            "serial_number": item.serial_number,
            "type": "service_item",
        }
        for item in items
    ]


def search_inventory_items(query, limit=10):
    """Search inventory items by name, SKU, or manufacturer.

    Excludes soft-deleted items.

    Args:
        query: The search text.
        limit: Maximum number of results to return.

    Returns:
        A list of dicts with 'id', 'name', 'sku', and 'type' keys.
    """
    if not query:
        return []

    pattern = f"%{query}%"
    items = (
        InventoryItem.not_deleted()
        .filter(
            or_(
                InventoryItem.name.ilike(pattern),
                InventoryItem.sku.ilike(pattern),
                InventoryItem.manufacturer.ilike(pattern),
            )
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "id": item.id,
            "name": item.name,
            "sku": item.sku,
            "type": "inventory_item",
        }
        for item in items
    ]
