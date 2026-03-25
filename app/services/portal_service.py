"""Portal service layer for customer-facing dashboard and tracking views."""

from flask import abort
from sqlalchemy.orm import selectinload

from app.models.service_note import ServiceNote
from app.models.service_order import ServiceOrder
from app.models.service_order_item import ServiceOrderItem
from app.services import audit_service, customer_service, order_service


PORTAL_ACTIVE_STATUSES = {
    "intake",
    "assessment",
    "awaiting_approval",
    "in_progress",
    "awaiting_parts",
    "ready_for_pickup",
}


def get_customer_orders(customer_id, active_only=None):
    """Return portal-visible orders for a customer."""
    return customer_service.get_customer_orders(customer_id, active_only=active_only)


def get_customer_dashboard(customer_id, active_limit=5, recent_limit=5):
    """Build the customer dashboard payload."""
    active_orders = _get_customer_active_orders(customer_id)
    all_orders = get_customer_orders(customer_id)

    return {
        "active_orders": [_serialize_order_card(order) for order in active_orders[:active_limit]],
        "recent_orders": [_serialize_order_card(order) for order in all_orders[:recent_limit]],
        "active_count": len(active_orders),
        "recent_count": len(all_orders),
    }


def get_customer_order(customer_id, order_id):
    """Return a single order for the customer or 404 if it does not belong to them."""
    order = (
        ServiceOrder.not_deleted()
        .filter_by(id=order_id, customer_id=customer_id)
        .one_or_none()
    )
    if order is None:
        abort(404)
    return order


def get_customer_order_detail(customer_id, order_id):
    """Return portal-safe detail data for a single order."""
    order = get_customer_order(customer_id, order_id)
    items = (
        ServiceOrderItem.query.filter_by(order_id=order.id)
        .options(selectinload(ServiceOrderItem.service_item))
        .order_by(ServiceOrderItem.id.asc())
        .all()
    )
    summary = order_service.get_order_summary(order.id)
    status_history = get_order_status_history(customer_id, order_id)
    public_notes = _get_public_notes_for_items(items)

    return {
        "order": order,
        "summary": summary,
        "items": [
            _serialize_order_item(item, public_notes.get(item.id, []), order.customer_id)
            for item in items
            if _is_portal_visible_item(item, order.customer_id)
        ],
        "status_history": status_history,
    }


def get_order_status_history(customer_id, order_id):
    """Return status-change history for the given customer order."""
    get_customer_order(customer_id, order_id)
    pagination = audit_service.get_audit_logs(
        entity_type="service_order",
        entity_id=order_id,
        action="status_change",
        per_page=100,
    )
    return [_serialize_status_change(entry) for entry in reversed(pagination.items)]


def _serialize_order_card(order):
    visible_items = [
        item
        for item in order.order_items.all()
        if _is_portal_visible_item(item, order.customer_id)
    ]
    item_names = [item.service_item.name for item in visible_items]
    summary = order_service.get_order_summary(order.id)
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "display_status": order.display_status,
        "date_received": order.date_received,
        "date_promised": order.date_promised,
        "date_completed": order.date_completed,
        "item_count": len(visible_items),
        "item_names": item_names[:3],
        "estimated_total": summary["estimated_total"],
        "is_overdue": order.is_overdue,
    }


def _get_customer_active_orders(customer_id):
    orders = get_customer_orders(customer_id)
    return [order for order in orders if order.status in PORTAL_ACTIVE_STATUSES]


def _is_portal_visible_item(order_item, customer_id):
    service_item = order_item.service_item
    return service_item is not None and service_item.customer_id == customer_id


def _serialize_order_item(order_item, public_notes, customer_id):
    service_item = order_item.service_item
    if service_item is None or service_item.customer_id != customer_id:
        return None
    return {
        "id": order_item.id,
        "status": order_item.status,
        "display_status": order_item.status.replace("_", " ").title() if order_item.status else "",
        "work_description": order_item.work_description,
        "condition_at_receipt": order_item.condition_at_receipt,
        "serviceability": service_item.serviceability,
        "serviceability_display": service_item.serviceability.replace("_", " ").title() if service_item.serviceability else "",
        "serial_number": service_item.serial_number,
        "name": service_item.name,
        "brand": service_item.brand,
        "model": service_item.model,
        "item_category": service_item.item_category,
        "last_service_date": service_item.last_service_date,
        "notes": public_notes,
    }


def _get_public_notes_for_items(items):
    if not items:
        return {}

    item_ids = [item.id for item in items]
    notes = (
        ServiceNote.query.filter(
            ServiceNote.service_order_item_id.in_(item_ids),
            ServiceNote.note_type == "customer_communication",
        )
        .order_by(ServiceNote.created_at.asc())
        .all()
    )

    grouped = {}
    for note in notes:
        grouped.setdefault(note.service_order_item_id, []).append(
            _serialize_public_note(note)
        )
    return grouped


def _serialize_public_note(note):
    return {
        "id": note.id,
        "note_text": note.note_text,
        "created_at": note.created_at,
    }


def _serialize_status_change(entry):
    return {
        "id": entry.id,
        "created_at": entry.created_at,
        "old_value": entry.old_value,
        "new_value": entry.new_value,
        "field_name": entry.field_name,
    }
