"""Notification service layer — business logic for in-app notifications.

Provides module-level functions for creating, querying, and managing
notifications.  Includes convenience helpers for domain-specific events
such as low-stock alerts, order status changes, and payment receipts.
"""

from datetime import datetime, timezone

from app.extensions import db
from app.models.notification import Notification
from app.models.user import Role, User


# =========================================================================
# Core CRUD
# =========================================================================

def create_notification(
    user_id,
    notification_type,
    title,
    message,
    entity_type=None,
    entity_id=None,
    severity="info",
):
    """Create and persist a new notification.

    Args:
        user_id: Target user ID, or None for a broadcast notification.
        notification_type: One of the VALID_NOTIFICATION_TYPES strings.
        title: Short summary displayed in the notification list.
        message: Full notification message body.
        entity_type: Optional entity type for navigation (e.g. 'order').
        entity_id: Optional entity primary key for navigation.
        severity: One of 'info', 'warning', 'critical'.  Defaults to 'info'.

    Returns:
        The newly created Notification instance.
    """
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
        severity=severity,
    )
    db.session.add(notification)
    db.session.commit()
    return notification


def get_notifications(user_id, unread_only=False, page=1, per_page=20):
    """Return paginated notifications for a user, newest first.

    Includes both user-targeted notifications and broadcast notifications
    (where user_id is NULL).

    Args:
        user_id: The user ID to fetch notifications for.
        unread_only: If True, return only unread notifications.
        page: Page number (1-indexed).
        per_page: Number of results per page.

    Returns:
        A SQLAlchemy pagination object.
    """
    query = Notification.query.filter(
        db.or_(
            Notification.user_id == user_id,
            Notification.user_id.is_(None),
        )
    )

    if unread_only:
        query = query.filter(Notification.is_read == False)  # noqa: E712

    query = query.order_by(Notification.created_at.desc())

    return db.paginate(query, page=page, per_page=per_page)


def get_unread_count(user_id):
    """Return the count of unread notifications for a user.

    Counts both user-targeted and broadcast notifications.

    Args:
        user_id: The user ID to count unread notifications for.

    Returns:
        An integer count of unread notifications.
    """
    return Notification.query.filter(
        db.or_(
            Notification.user_id == user_id,
            Notification.user_id.is_(None),
        ),
        Notification.is_read == False,  # noqa: E712
    ).count()


def mark_as_read(notification_id, user_id=None):
    """Mark a single notification as read.

    Sets ``is_read`` to True and records the ``read_at`` timestamp.

    When *user_id* is provided the function verifies that the notification
    belongs to that user before updating it.  Broadcast notifications
    (``notification.user_id is None``) may be marked as read by any user.

    Args:
        notification_id: The primary key of the notification.
        user_id: Optional user ID for ownership verification.  When given,
            the notification is only updated if it belongs to this user or
            is a broadcast notification.

    Returns:
        The updated Notification instance, or None if not found or if the
        ownership check fails.
    """
    notification = db.session.get(Notification, notification_id)
    if notification is None:
        return None

    if user_id is not None:
        if notification.user_id is not None and notification.user_id != user_id:
            return None

    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    db.session.commit()
    return notification


def mark_all_read(user_id):
    """Mark all unread notifications for a user as read.

    Updates both user-targeted and broadcast notifications.

    Args:
        user_id: The user ID whose notifications should be marked read.

    Returns:
        The number of notifications that were updated.
    """
    now = datetime.now(timezone.utc)
    count = Notification.query.filter(
        db.or_(
            Notification.user_id == user_id,
            Notification.user_id.is_(None),
        ),
        Notification.is_read == False,  # noqa: E712
    ).update(
        {"is_read": True, "read_at": now},
        synchronize_session="fetch",
    )
    db.session.commit()
    return count


# =========================================================================
# Domain-specific notification helpers
# =========================================================================

def _get_admin_user_ids():
    """Return a list of user IDs that have the 'admin' role.

    Returns:
        A list of integer user IDs.
    """
    admin_role = Role.query.filter_by(name="admin").first()
    if admin_role is None:
        return []
    return [u.id for u in admin_role.users.all()]


def notify_low_stock(inventory_item):
    """Create a low-stock notification for all admin users.

    Determines severity based on stock level: 'critical' if stock is zero
    or negative, 'warning' otherwise.

    Args:
        inventory_item: An InventoryItem instance that is below its
            reorder level.

    Returns:
        A list of created Notification instances.
    """
    if inventory_item.quantity_in_stock <= 0:
        severity = "critical"
        notification_type = "critical_stock"
        title = f"Critical stock: {inventory_item.name}"
        message = (
            f"{inventory_item.name} is out of stock "
            f"(current: {inventory_item.quantity_in_stock}, "
            f"reorder level: {inventory_item.reorder_level})."
        )
    else:
        severity = "warning"
        notification_type = "low_stock"
        title = f"Low stock: {inventory_item.name}"
        message = (
            f"{inventory_item.name} is below reorder level "
            f"(current: {inventory_item.quantity_in_stock}, "
            f"reorder level: {inventory_item.reorder_level})."
        )

    admin_ids = _get_admin_user_ids()
    notifications = []
    for admin_id in admin_ids:
        notification = create_notification(
            user_id=admin_id,
            notification_type=notification_type,
            title=title,
            message=message,
            entity_type="inventory_item",
            entity_id=inventory_item.id,
            severity=severity,
        )
        notifications.append(notification)

    return notifications


def notify_order_status_change(order, old_status, new_status):
    """Create notifications when an order's status changes.

    Notifies the assigned technician (if any) and all admin users.
    Avoids sending duplicate notifications if the tech is also an admin.

    Args:
        order: A ServiceOrder instance.
        old_status: The previous status string.
        new_status: The new status string.

    Returns:
        A list of created Notification instances.
    """
    display_old = old_status.replace("_", " ").title()
    display_new = new_status.replace("_", " ").title()

    title = f"Order {order.order_number} status changed"
    message = (
        f"Order {order.order_number} status changed "
        f"from {display_old} to {display_new}."
    )

    # Collect unique user IDs to notify
    notify_user_ids = set(_get_admin_user_ids())
    if order.assigned_tech_id is not None:
        notify_user_ids.add(order.assigned_tech_id)

    notifications = []
    for uid in notify_user_ids:
        notification = create_notification(
            user_id=uid,
            notification_type="order_status_change",
            title=title,
            message=message,
            entity_type="service_order",
            entity_id=order.id,
            severity="info",
        )
        notifications.append(notification)

    return notifications


def notify_payment_received(invoice, payment):
    """Create a notification for admin users when a payment is received.

    Args:
        invoice: An Invoice instance the payment was applied to.
        payment: A Payment instance that was recorded.

    Returns:
        A list of created Notification instances.
    """
    title = f"Payment received for invoice {invoice.invoice_number}"
    message = (
        f"A payment of ${payment.amount:.2f} was received for "
        f"invoice {invoice.invoice_number}. "
        f"Balance due: ${invoice.balance_due:.2f}."
    )

    admin_ids = _get_admin_user_ids()
    notifications = []
    for admin_id in admin_ids:
        notification = create_notification(
            user_id=admin_id,
            notification_type="payment_received",
            title=title,
            message=message,
            entity_type="invoice",
            entity_id=invoice.id,
            severity="info",
        )
        notifications.append(notification)

    return notifications
