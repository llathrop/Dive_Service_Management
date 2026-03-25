"""Portal service layer for customer-facing dashboard, tracking, and equipment views."""

from datetime import timedelta

from flask import abort
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models.attachment import Attachment
from app.models.customer import Customer
from app.models.portal_user import PortalAccessToken
from app.models.service_item import ServiceItem
from app.models.service_note import ServiceNote
from app.models.service_order import COMPLETED_STATUSES, ServiceOrder
from app.models.service_order_item import ServiceOrderItem
from app.services import attachment_service, audit_service, customer_service, item_service, order_service

PORTAL_ACTIVE_STATUSES = {
    "intake",
    "assessment",
    "awaiting_approval",
    "in_progress",
    "awaiting_parts",
    "ready_for_pickup",
}

PORTAL_MEDIA_ORDER_STATUSES = set(COMPLETED_STATUSES)
PORTAL_MEDIA_ORDER_STATUSES.update({"ready_for_pickup", "picked_up"})


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


def get_customer_portal_items(customer_id):
    """Return active equipment records for a customer."""
    return (
        ServiceItem.not_deleted()
        .filter_by(customer_id=customer_id)
        .order_by(
            ServiceItem.last_service_date.desc(),
            ServiceItem.name.asc(),
            ServiceItem.id.asc(),
        )
        .all()
    )


def get_customer_portal_item(customer_id, item_id):
    """Return a single customer-owned item or 404."""
    item = (
        ServiceItem.not_deleted()
        .filter_by(id=item_id, customer_id=customer_id)
        .one_or_none()
    )
    if item is None:
        abort(404)
    return item


def get_customer_portal_history(customer_id, item_id):
    """Return service history rows scoped to the customer."""
    item = get_customer_portal_item(customer_id, item_id)
    history = [
        oi
        for oi in item_service.get_service_history(item.id)
        if oi.order and oi.order.customer_id == customer_id
    ]
    return item, history


def get_customer_portal_media(customer_id, item_id):
    """Return customer-safe service-visit attachments.

    Direct service-item attachments are not exposed through the portal
    until there is explicit customer-safe metadata to distinguish them.
    """
    item = get_customer_portal_item(customer_id, item_id)
    _, order_groups = attachment_service.get_unified_attachments(item.id)

    safe_groups = []
    for group in order_groups:
        order = group["order"]
        if order is None or order.customer_id != customer_id:
            continue
        if order.status not in PORTAL_MEDIA_ORDER_STATUSES:
            continue
        safe_groups.append(group)

    return [], safe_groups


def get_portal_attachment(customer_id, item_id, attachment_id):
    """Return a portal-safe service visit attachment.

    Raw service-item attachments are intentionally not served.
    """
    item = get_customer_portal_item(customer_id, item_id)
    attachment = db.session.get(Attachment, attachment_id)
    if attachment is None:
        abort(404)

    if attachment.attachable_type == "service_item":
        abort(404)

    if attachment.attachable_type == "service_order_item":
        order_item = db.session.get(ServiceOrderItem, attachment.attachable_id)
        if (
            order_item is None
            or order_item.service_item_id != item.id
            or order_item.order is None
            or order_item.order.customer_id != customer_id
            or order_item.order.status not in PORTAL_MEDIA_ORDER_STATUSES
        ):
            abort(404)
        return attachment

    abort(404)


def get_customer_portal_invites(customer_id):
    """Return invite/access tokens for a customer, newest first."""
    return (
        PortalAccessToken.query.filter_by(customer_id=customer_id)
        .order_by(PortalAccessToken.created_at.desc())
        .all()
    )


def create_portal_invite(customer_id, email=None, expires_in=timedelta(hours=72)):
    """Create a portal invite token for a customer."""
    customer = db.session.get(Customer, customer_id)
    if customer is None:
        abort(404)

    invite_email = (email or customer.email or "").strip()
    if not invite_email:
        raise ValueError("An invite email address is required.")

    token, raw_token = PortalAccessToken.issue_activation(
        customer=customer,
        email=invite_email,
        expires_in=expires_in,
    )
    db.session.commit()
    return token, raw_token


def get_next_service_due(item):
    """Return the next service due date for an item, if calculable."""
    if not item.last_service_date or not item.service_interval_days:
        return None
    from datetime import timedelta as _timedelta

    return item.last_service_date + _timedelta(days=item.service_interval_days)
