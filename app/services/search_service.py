"""Search service layer -- global search across multiple entity types.

Provides module-level functions for searching customers, service items,
inventory items, service orders, and invoices using LIKE/ilike queries
(SQLite and MariaDB compatible).  Results include entity type, display
text, and URL path for direct navigation.
"""

from sqlalchemy import or_

from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.invoice import Invoice
from app.models.service_item import ServiceItem
from app.models.service_order import ServiceOrder


def global_search(query, limit=20):
    """Search across customers, service items, inventory, orders, and invoices.

    Returns a dict with results grouped by entity type.  Each result
    includes 'id', 'display_text', 'entity_type', and 'url' fields
    suitable for autocomplete and full search results.

    Args:
        query: The search text.  Must be at least 2 characters.
        limit: Maximum number of results per entity type.

    Returns:
        A dict with keys for each entity type, each containing a list
        of result dicts.
    """
    if not query or len(query.strip()) < 2:
        return {
            "customers": [],
            "service_items": [],
            "inventory_items": [],
            "orders": [],
            "invoices": [],
        }

    q = query.strip()

    return {
        "customers": search_customers(q, limit=limit),
        "service_items": search_service_items(q, limit=limit),
        "inventory_items": search_inventory_items(q, limit=limit),
        "orders": search_orders(q, limit=limit),
        "invoices": search_invoices(q, limit=limit),
    }


def search_customers(query, limit=10):
    """Search customers by name, business_name, email, or phone.

    Excludes soft-deleted customers.

    Args:
        query: The search text.
        limit: Maximum number of results to return.

    Returns:
        A list of dicts with 'id', 'display_text', 'entity_type', 'url',
        and legacy 'display_name'/'email' keys.
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
            "display_text": c.display_name,
            "display_name": c.display_name,
            "email": c.email,
            "entity_type": "customer",
            "type": "customer",
            "url": f"/customers/{c.id}",
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
        A list of dicts with 'id', 'display_text', 'entity_type', 'url',
        and legacy 'name'/'serial_number' keys.
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

    results = []
    for item in items:
        display = item.name
        if item.serial_number:
            display = f"{item.name} ({item.serial_number})"
        results.append({
            "id": item.id,
            "display_text": display,
            "name": item.name,
            "serial_number": item.serial_number,
            "entity_type": "service_item",
            "type": "service_item",
            "url": f"/items/{item.id}",
        })

    return results


def search_inventory_items(query, limit=10):
    """Search inventory items by name, SKU, or manufacturer.

    Excludes soft-deleted items.

    Args:
        query: The search text.
        limit: Maximum number of results to return.

    Returns:
        A list of dicts with 'id', 'display_text', 'entity_type', 'url',
        and legacy 'name'/'sku' keys.
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

    results = []
    for item in items:
        display = item.name
        if item.sku:
            display = f"{item.name} ({item.sku})"
        results.append({
            "id": item.id,
            "display_text": display,
            "name": item.name,
            "sku": item.sku,
            "entity_type": "inventory_item",
            "type": "inventory_item",
            "url": f"/inventory/{item.id}",
        })

    return results


def search_orders(query, limit=10):
    """Search service orders by order number, description, or customer name.

    Excludes soft-deleted orders.

    Args:
        query: The search text.
        limit: Maximum number of results to return.

    Returns:
        A list of dicts with 'id', 'display_text', 'entity_type', and 'url'.
    """
    if not query:
        return []

    pattern = f"%{query}%"
    orders = (
        ServiceOrder.not_deleted()
        .filter(
            or_(
                ServiceOrder.order_number.ilike(pattern),
                ServiceOrder.description.ilike(pattern),
            )
        )
        .limit(limit)
        .all()
    )

    results = []
    for o in orders:
        customer_name = o.customer.display_name if o.customer else "Unknown"
        display = f"{o.order_number} - {customer_name}"
        results.append({
            "id": o.id,
            "display_text": display,
            "entity_type": "order",
            "type": "order",
            "url": f"/orders/{o.id}",
            "order_number": o.order_number,
            "status": o.status,
        })

    return results


def search_invoices(query, limit=10):
    """Search invoices by invoice number or customer name.

    Args:
        query: The search text.
        limit: Maximum number of results to return.

    Returns:
        A list of dicts with 'id', 'display_text', 'entity_type', and 'url'.
    """
    if not query:
        return []

    pattern = f"%{query}%"
    invoices = (
        Invoice.query
        .filter(
            or_(
                Invoice.invoice_number.ilike(pattern),
            )
        )
        .limit(limit)
        .all()
    )

    results = []
    for inv in invoices:
        customer_name = inv.customer.display_name if inv.customer else "Unknown"
        display = f"{inv.invoice_number} - {customer_name}"
        results.append({
            "id": inv.id,
            "display_text": display,
            "entity_type": "invoice",
            "type": "invoice",
            "url": f"/invoices/{inv.id}",
            "invoice_number": inv.invoice_number,
            "status": inv.status,
        })

    return results
