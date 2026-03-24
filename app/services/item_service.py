"""Service item service layer — business logic for service item management.

Provides module-level functions for CRUD operations on service items
(customer-owned dive equipment) including drysuit detail management
and serial number lookup.  All queries exclude soft-deleted records
by default.
"""

from flask import abort
from sqlalchemy import or_

from app.extensions import db
from app.models.drysuit_details import DrysuitDetails
from app.models.service_item import ServiceItem


# Drysuit detail fields that can be set from form data
DRYSUIT_FIELDS = [
    "size", "material_type", "material_thickness", "color",
    "suit_entry_type", "neck_seal_type", "neck_seal_system",
    "wrist_seal_type", "wrist_seal_system", "zipper_type",
    "zipper_length", "zipper_orientation", "inflate_valve_brand",
    "inflate_valve_model", "inflate_valve_position", "dump_valve_brand",
    "dump_valve_model", "dump_valve_type", "boot_type", "boot_size",
]


def get_items(
    page=1,
    per_page=25,
    search=None,
    sort="name",
    order="asc",
):
    """Return paginated, filtered, sorted service items.

    Args:
        page: Page number (1-indexed).
        per_page: Number of results per page.
        search: Optional search string (matches name, serial_number,
            brand, model).
        sort: Column name to sort by.  Defaults to 'name'.
        order: Sort direction, 'asc' or 'desc'.

    Returns:
        A SQLAlchemy pagination object.
    """
    query = ServiceItem.not_deleted()

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                ServiceItem.name.ilike(pattern),
                ServiceItem.serial_number.ilike(pattern),
                ServiceItem.brand.ilike(pattern),
                ServiceItem.model.ilike(pattern),
            )
        )

    # Apply sorting
    sort_column = getattr(ServiceItem, sort, ServiceItem.name)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    return db.paginate(query, page=page, per_page=per_page)


def get_item(item_id):
    """Return a single service item by ID or raise 404.

    Args:
        item_id: The primary key of the service item.

    Returns:
        A ServiceItem instance.

    Raises:
        404 HTTPException if the item does not exist or is soft-deleted.
    """
    item = db.session.get(ServiceItem, item_id)
    if item is None or item.is_deleted:
        abort(404)
    return item


def create_item(data, drysuit_data=None, created_by=None):
    """Create a new service item from a data dict.

    If the item_category is 'Drysuit' and drysuit_data is provided,
    also creates the associated DrysuitDetails record.

    Args:
        data: Dictionary of service item fields.
        drysuit_data: Optional dictionary of drysuit detail fields.
        created_by: Optional user ID of the creator.

    Returns:
        The newly created ServiceItem instance.
    """
    item = ServiceItem(
        serial_number=data.get("serial_number") or None,
        name=data["name"],
        item_category=data.get("item_category"),
        serviceability=data.get("serviceability", "serviceable"),
        serviceability_notes=data.get("serviceability_notes"),
        brand=data.get("brand"),
        model=data.get("model"),
        year_manufactured=data.get("year_manufactured"),
        notes=data.get("notes"),
        service_interval_days=data.get("service_interval_days"),
        customer_id=data.get("customer_id") or None,
        created_by=created_by,
    )
    db.session.add(item)
    db.session.flush()

    # Create drysuit details if category is Drysuit
    if data.get("item_category") == "Drysuit" and drysuit_data:
        drysuit = DrysuitDetails(service_item_id=item.id)
        _populate_drysuit(drysuit, drysuit_data)
        db.session.add(drysuit)

    db.session.commit()
    return item


def update_item(item_id, data, drysuit_data=None):
    """Update an existing service item from a data dict.

    Handles drysuit details: creates, updates, or removes them based
    on the item_category value.

    Args:
        item_id: The primary key of the item to update.
        data: Dictionary of fields to update.
        drysuit_data: Optional dictionary of drysuit detail fields.

    Returns:
        The updated ServiceItem instance.

    Raises:
        404 HTTPException if the item does not exist.
    """
    item = get_item(item_id)

    for field in (
        "serial_number",
        "name",
        "item_category",
        "serviceability",
        "serviceability_notes",
        "brand",
        "model",
        "year_manufactured",
        "notes",
        "service_interval_days",
        "customer_id",
    ):
        if field in data:
            setattr(item, field, data[field])

    # Ensure empty serial number is stored as None (unique constraint)
    if not item.serial_number:
        item.serial_number = None

    # Handle drysuit details based on category
    if data.get("item_category") == "Drysuit":
        if item.drysuit_details is None:
            drysuit = DrysuitDetails(service_item_id=item.id)
            db.session.add(drysuit)
            item.drysuit_details = drysuit
        if drysuit_data:
            _populate_drysuit(item.drysuit_details, drysuit_data)
    else:
        # Remove drysuit details if category changed away from Drysuit
        if item.drysuit_details is not None:
            db.session.delete(item.drysuit_details)

    db.session.commit()
    return item


def delete_item(item_id):
    """Soft-delete a service item.

    Args:
        item_id: The primary key of the item to delete.

    Returns:
        The soft-deleted ServiceItem instance.

    Raises:
        404 HTTPException if the item does not exist.
    """
    item = get_item(item_id)
    item.soft_delete()
    db.session.commit()
    return item


def lookup_by_serial(serial_number):
    """Look up a service item by serial number.

    Args:
        serial_number: The serial number to search for.

    Returns:
        A ServiceItem instance, or None if not found.
    """
    if not serial_number:
        return None
    return ServiceItem.not_deleted().filter_by(serial_number=serial_number).first()


def get_service_history(item_id):
    """Return ServiceOrderItems for this item with their orders, newest first."""
    from app.models.service_order import ServiceOrder
    from app.models.service_order_item import ServiceOrderItem

    return (
        db.session.query(ServiceOrderItem)
        .join(ServiceOrder)
        .filter(ServiceOrderItem.service_item_id == item_id)
        .filter(ServiceOrder.is_deleted == False)  # noqa: E712
        .order_by(ServiceOrder.date_received.desc())
        .all()
    )


def _populate_drysuit(drysuit, data):
    """Copy drysuit data (dict) onto a DrysuitDetails instance.

    Args:
        drysuit: A DrysuitDetails instance.
        data: A dictionary of field_name -> value pairs.
    """
    for field_name in DRYSUIT_FIELDS:
        if field_name in data:
            setattr(drysuit, field_name, data[field_name] or None)
