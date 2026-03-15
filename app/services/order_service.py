"""Order service layer — core business logic for the service workflow.

Provides module-level functions for managing service orders, order items,
applied services, parts used, labor entries, service notes, status
transitions, and order summary calculations.  This is the most complex
service in the application, orchestrating the full lifecycle of a
service work order from intake through pickup.

All queries exclude soft-deleted records by default.
"""

import re
from datetime import date
from decimal import Decimal

from flask import abort
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.applied_service import AppliedService
from app.models.inventory import InventoryItem
from app.models.labor import LaborEntry
from app.models.parts_used import PartUsed
from app.models.price_list import PriceListItem
from app.models.service_note import ServiceNote
from app.models.service_order import ServiceOrder
from app.models.service_order_item import ServiceOrderItem
from app.services import audit_service


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATUS_TRANSITIONS = {
    "intake": ["assessment", "cancelled"],
    "assessment": ["awaiting_approval", "in_progress", "cancelled"],
    "awaiting_approval": ["in_progress", "cancelled"],
    "in_progress": ["awaiting_parts", "completed", "cancelled"],
    "awaiting_parts": ["in_progress", "cancelled"],
    "completed": ["ready_for_pickup"],
    "ready_for_pickup": ["picked_up"],
    "picked_up": [],  # terminal state
    "cancelled": ["intake"],  # can reopen
}

SORTABLE_FIELDS = [
    "order_number",
    "status",
    "priority",
    "date_received",
    "date_promised",
    "estimated_total",
    "created_at",
]

ORDER_NUMBER_PATTERN = re.compile(r"^SO-(\d{4})-(\d{5})$")


# =========================================================================
# Order CRUD
# =========================================================================

def get_orders(
    page=1,
    per_page=25,
    search=None,
    status=None,
    priority=None,
    assigned_tech_id=None,
    date_from=None,
    date_to=None,
    sort="date_received",
    order="desc",
):
    """Return paginated, filtered, sorted service orders.

    Args:
        page: Page number (1-indexed).
        per_page: Number of results per page.
        search: Optional search string (matches order_number, description).
        status: Optional status filter.
        priority: Optional priority filter.
        assigned_tech_id: Optional technician ID filter.
        date_from: Optional start date for date_received range.
        date_to: Optional end date for date_received range.
        sort: Column name to sort by.  Must be in SORTABLE_FIELDS.
        order: Sort direction, 'asc' or 'desc'.

    Returns:
        A SQLAlchemy pagination object.
    """
    query = ServiceOrder.not_deleted()

    # Apply search filter
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                ServiceOrder.order_number.ilike(pattern),
                ServiceOrder.description.ilike(pattern),
            )
        )

    # Apply status filter
    if status:
        query = query.filter(ServiceOrder.status == status)

    # Apply priority filter
    if priority:
        query = query.filter(ServiceOrder.priority == priority)

    # Apply assigned technician filter
    if assigned_tech_id is not None:
        query = query.filter(ServiceOrder.assigned_tech_id == assigned_tech_id)

    # Apply date range filters
    if date_from is not None:
        query = query.filter(ServiceOrder.date_received >= date_from)
    if date_to is not None:
        query = query.filter(ServiceOrder.date_received <= date_to)

    # Apply sorting (validate against allowlist)
    if sort not in SORTABLE_FIELDS:
        sort = "date_received"
    sort_column = getattr(ServiceOrder, sort, ServiceOrder.date_received)
    if order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    return db.paginate(query, page=page, per_page=per_page)


def get_order(order_id):
    """Return a single service order by ID or raise 404.

    Args:
        order_id: The primary key of the service order.

    Returns:
        A ServiceOrder instance.

    Raises:
        404 HTTPException if the order does not exist or is soft-deleted.
    """
    order = db.session.get(ServiceOrder, order_id)
    if order is None or order.is_deleted:
        abort(404)
    return order


def create_order(data, created_by=None, ip_address=None, user_agent=None):
    """Create a new service order from a data dict.

    Auto-generates the order_number using the SO-YYYY-NNNNN pattern.

    Args:
        data: Dictionary of service order fields.
        created_by: Optional user ID of the creator.
        ip_address: Optional IP address for audit logging.
        user_agent: Optional user agent for audit logging.

    Returns:
        The newly created ServiceOrder instance.
    """
    order = ServiceOrder(
        customer_id=data["customer_id"],
        status=data.get("status", "intake"),
        priority=data.get("priority", "normal"),
        assigned_tech_id=data.get("assigned_tech_id"),
        date_received=data.get("date_received", date.today()),
        date_promised=data.get("date_promised"),
        description=data.get("description"),
        internal_notes=data.get("internal_notes"),
        estimated_total=data.get("estimated_total"),
        rush_fee=data.get("rush_fee", Decimal("0.00")),
        discount_percent=data.get("discount_percent", Decimal("0.00")),
        discount_amount=data.get("discount_amount", Decimal("0.00")),
        created_by=created_by,
    )

    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            order.order_number = generate_order_number()
            db.session.add(order)
            db.session.flush()
            break
        except IntegrityError:
            db.session.rollback()
            if attempt == MAX_RETRIES - 1:
                raise

    db.session.commit()
    try:
        audit_service.log_action(
            action="create",
            entity_type="service_order",
            entity_id=order.id,
            user_id=created_by,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass
    return order


def update_order(order_id, data, user_id=None, ip_address=None, user_agent=None):
    """Update an existing service order from a data dict.

    Args:
        order_id: The primary key of the order to update.
        data: Dictionary of fields to update.
        user_id: Optional user ID for audit logging.
        ip_address: Optional IP address for audit logging.
        user_agent: Optional user agent for audit logging.

    Returns:
        The updated ServiceOrder instance.

    Raises:
        404 HTTPException if the order does not exist.
    """
    order = get_order(order_id)

    for field in (
        "customer_id",
        "assigned_tech_id",
        "date_received",
        "date_promised",
        "date_completed",
        "date_picked_up",
        "description",
        "internal_notes",
        "estimated_total",
        "rush_fee",
        "discount_percent",
        "discount_amount",
        "actual_total",
        "approved_at",
        "approved_by_name",
        "approval_method",
        "picked_up_by_name",
        "pickup_notes",
    ):
        if field in data:
            setattr(order, field, data[field])

    # Priority requires explicit validation; status must go through change_status().
    if "priority" in data:
        valid_priorities = {"low", "normal", "high", "rush"}
        if data["priority"] in valid_priorities:
            order.priority = data["priority"]

    db.session.commit()
    try:
        audit_service.log_action(
            action="update",
            entity_type="service_order",
            entity_id=order.id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass
    return order


def delete_order(order_id, user_id=None, ip_address=None, user_agent=None):
    """Soft-delete a service order.

    Args:
        order_id: The primary key of the order to delete.
        user_id: Optional user ID for audit logging.
        ip_address: Optional IP address for audit logging.
        user_agent: Optional user agent for audit logging.

    Returns:
        The soft-deleted ServiceOrder instance.

    Raises:
        404 HTTPException if the order does not exist.
    """
    order = get_order(order_id)
    order.soft_delete()
    db.session.commit()
    try:
        audit_service.log_action(
            action="delete",
            entity_type="service_order",
            entity_id=order.id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass
    return order


# =========================================================================
# Order Number Generation
# =========================================================================

def generate_order_number():
    """Generate the next sequential order number for the current year.

    Format: SO-{YEAR}-{SEQUENCE:05d}, e.g. "SO-2026-00001".

    Queries the maximum existing order_number for the current year,
    extracts the sequence portion, and increments it.  Falls back to
    a count-based approach if existing numbers don't match the expected
    pattern.

    Returns:
        A string like "SO-2026-00001".
    """
    current_year = date.today().year
    prefix = f"SO-{current_year}-"

    # Find the max order_number for the current year
    result = (
        db.session.query(ServiceOrder.order_number)
        .filter(ServiceOrder.order_number.like(f"{prefix}%"))
        .order_by(ServiceOrder.order_number.desc())
        .first()
    )

    if result is not None:
        match = ORDER_NUMBER_PATTERN.match(result[0])
        if match and int(match.group(1)) == current_year:
            next_seq = int(match.group(2)) + 1
        else:
            # Fallback: count existing orders with this year's prefix
            count = (
                db.session.query(func.count(ServiceOrder.id))
                .filter(ServiceOrder.order_number.like(f"{prefix}%"))
                .scalar()
            )
            next_seq = count + 1
    else:
        next_seq = 1

    return f"{prefix}{next_seq:05d}"


# =========================================================================
# Status Workflow
# =========================================================================

def change_status(order_id, new_status, user_id=None, ip_address=None, user_agent=None):
    """Transition a service order to a new status.

    Validates that the transition is allowed according to the
    STATUS_TRANSITIONS map.  Sets date_completed when transitioning
    to 'completed' and date_picked_up when transitioning to 'picked_up'.

    Args:
        order_id: The primary key of the order.
        new_status: The target status string.
        user_id: Optional user ID performing the transition.
        ip_address: Optional IP address for audit logging.
        user_agent: Optional user agent for audit logging.

    Returns:
        A tuple of (order, success).  ``success`` is True if the
        transition was valid and applied, False otherwise.
    """
    order = get_order(order_id)

    if not new_status:
        return (order, False)

    current_status = order.status

    allowed = STATUS_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        return (order, False)

    order.status = new_status

    # Set milestone dates
    if new_status == "completed":
        order.date_completed = date.today()
    elif new_status == "picked_up":
        order.date_picked_up = date.today()

    db.session.commit()
    try:
        audit_service.log_action(
            action="status_change",
            entity_type="service_order",
            entity_id=order.id,
            user_id=user_id,
            field_name="status",
            old_value=current_status,
            new_value=new_status,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass
    return (order, True)


# =========================================================================
# Order Items
# =========================================================================

def add_order_item(order_id, service_item_id, work_description=None, condition_at_receipt=None):
    """Add a service item to an order.

    Creates a ServiceOrderItem linking the service item to the order.

    Args:
        order_id: The primary key of the order.
        service_item_id: The primary key of the service item.
        work_description: Optional description of work to be performed.
        condition_at_receipt: Optional description of item condition.

    Returns:
        The newly created ServiceOrderItem.

    Raises:
        ValueError: If the service item is already on this order.
    """
    existing = (
        ServiceOrderItem.query
        .filter_by(order_id=order_id, service_item_id=service_item_id)
        .first()
    )
    if existing is not None:
        raise ValueError(
            f"Service item {service_item_id} is already on order {order_id}."
        )

    order_item = ServiceOrderItem(
        order_id=order_id,
        service_item_id=service_item_id,
        work_description=work_description,
        condition_at_receipt=condition_at_receipt,
    )
    db.session.add(order_item)
    db.session.commit()
    try:
        audit_service.log_action(
            action="create",
            entity_type="service_order_item",
            entity_id=order_item.id,
            additional_data=f'{{"order_id": {order_id}}}',
        )
    except Exception:
        pass
    return order_item


def remove_order_item(order_item_id):
    """Remove a service order item and all its related records.

    Hard-deletes the ServiceOrderItem along with its cascaded children
    (notes, parts_used, labor_entries, applied_services).

    Args:
        order_item_id: The primary key of the order item.

    Returns:
        True if the item was found and deleted, False otherwise.
    """
    order_item = db.session.get(ServiceOrderItem, order_item_id)
    if order_item is None:
        return False

    order_id = order_item.order_id

    # Restore inventory for any parts_used before cascade deletes them
    for part in order_item.parts_used.all():
        inv_item = db.session.get(InventoryItem, part.inventory_item_id)
        if inv_item is not None:
            inv_item.quantity_in_stock += part.quantity

    db.session.delete(order_item)
    db.session.commit()
    try:
        audit_service.log_action(
            action="delete",
            entity_type="service_order_item",
            entity_id=order_item_id,
            additional_data=f'{{"order_id": {order_id}}}',
        )
    except Exception:
        pass
    return True


def get_order_item(order_item_id):
    """Return a single service order item by ID.

    Args:
        order_item_id: The primary key of the order item.

    Returns:
        A ServiceOrderItem instance, or None if not found.
    """
    return db.session.get(ServiceOrderItem, order_item_id)


# =========================================================================
# Applied Services
# =========================================================================

def add_applied_service(order_item_id, data, added_by=None):
    """Add an applied service to a service order item.

    If a price_list_item_id is provided, snapshots the name, description,
    and price from the PriceListItem.  Calculates line_total using the
    model's calculate_line_total() method.  If the price list item has
    auto_deduct_parts=True, automatically adds linked parts to parts_used.

    Args:
        order_item_id: The primary key of the order item.
        data: Dictionary of applied service fields.  May include:
            - price_list_item_id (optional)
            - service_name (required if no price_list_item_id)
            - service_description
            - quantity
            - unit_price (required if no price_list_item_id)
            - discount_percent
            - is_taxable
            - price_overridden
            - customer_approved
            - notes
        added_by: Optional user ID of the person adding the service.

    Returns:
        The newly created AppliedService instance.
    """
    price_list_item = None
    price_list_item_id = data.get("price_list_item_id")

    if price_list_item_id:
        price_list_item = db.session.get(PriceListItem, price_list_item_id)

    # Snapshot from price list item if available
    service_name = data.get("service_name")
    service_description = data.get("service_description")
    unit_price = data.get("unit_price")
    quantity = data.get("quantity", Decimal("1"))
    is_taxable = data.get("is_taxable", True)

    if price_list_item is not None:
        if not service_name:
            service_name = price_list_item.name
        if service_description is None:
            service_description = price_list_item.description
        if unit_price is None:
            unit_price = price_list_item.price
        is_taxable = data.get("is_taxable", price_list_item.is_taxable)

    applied = AppliedService(
        service_order_item_id=order_item_id,
        price_list_item_id=price_list_item_id,
        service_name=service_name,
        service_description=service_description,
        quantity=quantity,
        unit_price=unit_price,
        discount_percent=data.get("discount_percent", Decimal("0.00")),
        is_taxable=is_taxable,
        price_overridden=data.get("price_overridden", False),
        customer_approved=data.get("customer_approved", False),
        notes=data.get("notes"),
        added_by=added_by,
        line_total=Decimal("0"),  # placeholder, calculated below
    )

    applied.calculate_line_total()
    db.session.add(applied)
    db.session.flush()  # get the applied.id before creating parts_used

    # Auto-deduct linked parts if the price list item has auto_deduct_parts
    if price_list_item is not None and price_list_item.auto_deduct_parts:
        for linked_part in price_list_item.linked_parts.all():
            inv_item = db.session.get(InventoryItem, linked_part.inventory_item_id)
            if inv_item is not None:
                part_qty = linked_part.quantity
                add_part_used(
                    order_item_id=order_item_id,
                    inventory_item_id=linked_part.inventory_item_id,
                    quantity=part_qty,
                    unit_price_at_use=inv_item.resale_price,
                    added_by=added_by,
                    applied_service_id=applied.id,
                    is_auto_deducted=True,
                )

    db.session.commit()
    try:
        audit_service.log_action(
            action="create",
            entity_type="applied_service",
            entity_id=applied.id,
            user_id=added_by,
        )
    except Exception:
        pass
    return applied


def remove_applied_service(applied_service_id):
    """Remove an applied service and its auto-deducted parts.

    Deletes the AppliedService record.  Any parts_used linked to it
    that were auto-deducted are also deleted and their inventory
    quantities are restored.

    Args:
        applied_service_id: The primary key of the applied service.

    Returns:
        True if the applied service was found and deleted, False otherwise.
    """
    applied = db.session.get(AppliedService, applied_service_id)
    if applied is None:
        return False

    # Remove auto-deducted parts and restore inventory
    auto_parts = (
        PartUsed.query
        .filter_by(applied_service_id=applied_service_id, is_auto_deducted=True)
        .all()
    )
    for part in auto_parts:
        inv_item = db.session.get(InventoryItem, part.inventory_item_id)
        if inv_item is not None:
            inv_item.quantity_in_stock += part.quantity
        db.session.delete(part)

    db.session.delete(applied)
    db.session.commit()
    try:
        audit_service.log_action(
            action="delete",
            entity_type="applied_service",
            entity_id=applied_service_id,
        )
    except Exception:
        pass
    return True


# =========================================================================
# Parts Used
# =========================================================================

def add_part_used(
    order_item_id,
    inventory_item_id,
    quantity,
    unit_price_at_use=None,
    notes=None,
    added_by=None,
    applied_service_id=None,
    is_auto_deducted=False,
):
    """Record a part used on a service order item.

    Snapshots the unit_cost_at_use from the InventoryItem's purchase_cost.
    If unit_price_at_use is not provided, uses the InventoryItem's
    resale_price.  Deducts the quantity from inventory stock.

    Args:
        order_item_id: The primary key of the order item.
        inventory_item_id: The primary key of the inventory item.
        quantity: The quantity used.
        unit_price_at_use: Optional override for the price charged.
            Defaults to the inventory item's resale_price.
        notes: Optional notes about the part usage.
        added_by: Optional user ID of the person adding the part.
        applied_service_id: Optional link to an AppliedService (for
            auto-deducted parts).
        is_auto_deducted: Whether this part was auto-deducted from an
            applied service's linked parts.

    Returns:
        The newly created PartUsed instance.

    Raises:
        ValueError: If inventory item not found or insufficient stock.
    """
    inv_item = db.session.get(InventoryItem, inventory_item_id)
    if inv_item is None:
        raise ValueError(f"Inventory item {inventory_item_id} not found.")

    # Prevent deductions that would drive stock negative
    new_stock = inv_item.quantity_in_stock - quantity
    if new_stock < 0:
        raise ValueError(
            f"Insufficient stock for '{inv_item.name}': "
            f"have {inv_item.quantity_in_stock}, need {quantity}."
        )

    # Snapshot cost from inventory
    unit_cost = inv_item.purchase_cost if inv_item.purchase_cost is not None else Decimal("0.00")

    # Use resale_price as default sale price
    if unit_price_at_use is None:
        unit_price_at_use = inv_item.resale_price if inv_item.resale_price is not None else Decimal("0.00")

    part = PartUsed(
        service_order_item_id=order_item_id,
        inventory_item_id=inventory_item_id,
        applied_service_id=applied_service_id,
        is_auto_deducted=is_auto_deducted,
        quantity=quantity,
        unit_cost_at_use=unit_cost,
        unit_price_at_use=unit_price_at_use,
        notes=notes,
        added_by=added_by,
    )
    db.session.add(part)

    # Deduct from inventory stock (already validated non-negative above)
    inv_item.quantity_in_stock = new_stock

    # Only commit if this is a standalone call (not nested inside
    # add_applied_service which manages its own commit).
    if not is_auto_deducted:
        db.session.commit()
        try:
            audit_service.log_action(
                action="create",
                entity_type="part_used",
                entity_id=part.id,
                user_id=added_by,
                field_name="quantity_in_stock",
                old_value=str(inv_item.quantity_in_stock + quantity),
                new_value=str(inv_item.quantity_in_stock),
            )
        except Exception:
            pass

    return part


def remove_part_used(part_used_id):
    """Remove a part used record and restore inventory.

    Deletes the PartUsed record and adds the quantity back to the
    InventoryItem's quantity_in_stock.

    Args:
        part_used_id: The primary key of the PartUsed record.

    Returns:
        True if the record was found and deleted, False otherwise.
    """
    part = db.session.get(PartUsed, part_used_id)
    if part is None:
        return False

    # Restore inventory
    inv_item = db.session.get(InventoryItem, part.inventory_item_id)
    if inv_item is not None:
        inv_item.quantity_in_stock += part.quantity

    db.session.delete(part)
    db.session.commit()
    try:
        audit_service.log_action(
            action="delete",
            entity_type="part_used",
            entity_id=part_used_id,
        )
    except Exception:
        pass
    return True


# =========================================================================
# Labor Entries
# =========================================================================

def add_labor_entry(order_item_id, tech_id, hours, hourly_rate, description=None, work_date=None):
    """Add a labor entry to a service order item.

    Args:
        order_item_id: The primary key of the order item.
        tech_id: The user ID of the technician.
        hours: Number of hours worked (Decimal).
        hourly_rate: Hourly rate at time of entry (Decimal).
        description: Optional description of work performed.
        work_date: Date the work was performed.  Defaults to today.

    Returns:
        The newly created LaborEntry instance.
    """
    if work_date is None:
        work_date = date.today()

    entry = LaborEntry(
        service_order_item_id=order_item_id,
        tech_id=tech_id,
        hours=hours,
        hourly_rate=hourly_rate,
        description=description,
        work_date=work_date,
    )
    db.session.add(entry)
    db.session.commit()
    try:
        audit_service.log_action(
            action="create",
            entity_type="labor_entry",
            entity_id=entry.id,
            user_id=tech_id,
        )
    except Exception:
        pass
    return entry


def remove_labor_entry(labor_entry_id):
    """Remove a labor entry.

    Hard-deletes the LaborEntry record.

    Args:
        labor_entry_id: The primary key of the LaborEntry.

    Returns:
        True if the entry was found and deleted, False otherwise.
    """
    entry = db.session.get(LaborEntry, labor_entry_id)
    if entry is None:
        return False

    db.session.delete(entry)
    db.session.commit()
    try:
        audit_service.log_action(
            action="delete",
            entity_type="labor_entry",
            entity_id=labor_entry_id,
        )
    except Exception:
        pass
    return True


# =========================================================================
# Service Notes
# =========================================================================

def add_service_note(order_item_id, note_text, note_type="general", created_by=None):
    """Add a note to a service order item.

    Args:
        order_item_id: The primary key of the order item.
        note_text: The text content of the note.
        note_type: The type of note (e.g. 'general', 'diagnostic',
            'repair', 'testing', 'customer_communication').
        created_by: The user ID of the note author.

    Returns:
        The newly created ServiceNote instance.
    """
    note = ServiceNote(
        service_order_item_id=order_item_id,
        note_text=note_text,
        note_type=note_type,
        created_by=created_by,
    )
    db.session.add(note)
    db.session.commit()
    try:
        audit_service.log_action(
            action="create",
            entity_type="service_note",
            entity_id=note.id,
            user_id=created_by,
        )
    except Exception:
        pass
    return note


# =========================================================================
# Order Summary Calculations
# =========================================================================

def get_order_summary(order_id):
    """Calculate a financial summary for a service order.

    Aggregates totals across all order items for applied services,
    non-auto-deducted parts, and labor.  Applies the order-level
    rush fee, discount percent, and discount amount.

    Args:
        order_id: The primary key of the service order.

    Returns:
        A dict with keys:
            - applied_services_total
            - parts_total
            - labor_total
            - rush_fee
            - discount_amount
            - discount_percent
            - subtotal
            - discount_total
            - estimated_total
    """
    order = get_order(order_id)

    applied_services_total = Decimal("0.00")
    parts_total = Decimal("0.00")
    labor_total = Decimal("0.00")

    for order_item in order.order_items.all():
        # Sum applied services
        for svc in order_item.applied_services.all():
            if svc.line_total is not None:
                applied_services_total += Decimal(str(svc.line_total))

        # Sum non-auto-deducted parts
        for part in order_item.parts_used.all():
            if not part.is_auto_deducted and part.line_total is not None:
                parts_total += Decimal(str(part.line_total))

        # Sum labor
        for entry in order_item.labor_entries.all():
            if entry.line_total is not None:
                labor_total += Decimal(str(entry.line_total))

    rush_fee = Decimal(str(order.rush_fee)) if order.rush_fee is not None else Decimal("0.00")
    discount_amount = Decimal(str(order.discount_amount)) if order.discount_amount is not None else Decimal("0.00")
    discount_percent = Decimal(str(order.discount_percent)) if order.discount_percent is not None else Decimal("0.00")

    subtotal = applied_services_total + parts_total + labor_total + rush_fee

    # Calculate total discount
    percent_discount = subtotal * (discount_percent / Decimal("100"))
    discount_total = percent_discount + discount_amount

    estimated_total = subtotal - discount_total

    return {
        "applied_services_total": applied_services_total,
        "parts_total": parts_total,
        "labor_total": labor_total,
        "rush_fee": rush_fee,
        "discount_amount": discount_amount,
        "discount_percent": discount_percent,
        "subtotal": subtotal,
        "discount_total": discount_total,
        "estimated_total": estimated_total,
    }
