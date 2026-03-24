"""Recurring service reminder logic.

This module contains the plain reminder workflow used by both the
Celery task wrapper and the test suite.  Keeping the business logic
separate from Celery avoids coupling the tests to the module-level
Celery app created for worker/beat registration.
"""

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.notification import Notification
from app.models.service_reminder_delivery import ServiceReminderDelivery

logger = logging.getLogger(__name__)

REMINDER_WINDOW_DAYS = 30
REMINDER_COOLDOWN_DAYS = 30


def check_service_reminders():
    """Check service items and create reminder notifications when due.

    For each non-deleted item where ``service_interval_days`` and
    ``last_service_date`` are both set, calculates the next service due
    date.  If the item is due within the next 30 days (or overdue),
    notifications are created for each admin user who has not already
    received a reminder for that item within the last 30 days.

    Returns:
        Number of reminder notifications sent.
    """
    from app.models.service_item import ServiceItem
    from app.services import notification_service

    now = datetime.now(timezone.utc)
    today = now.date()
    reminder_window = today + timedelta(days=REMINDER_WINDOW_DAYS)
    recent_cutoff = now - timedelta(days=REMINDER_COOLDOWN_DAYS)

    items = (
        ServiceItem.not_deleted()
        .filter(
            ServiceItem.service_interval_days.isnot(None),
            ServiceItem.last_service_date.isnot(None),
        )
        .all()
    )

    admin_ids = notification_service._get_admin_user_ids()
    reminders_sent = 0

    for item in items:
        next_service_date = item.last_service_date + timedelta(
            days=item.service_interval_days
        )

        if next_service_date > reminder_window:
            continue

        if next_service_date <= today:
            severity = "warning"
            status_text = f"overdue (was due {next_service_date.isoformat()})"
        else:
            severity = "info"
            status_text = f"due {next_service_date.isoformat()}"

        customer_name = (
            item.customer.display_name if item.customer else "Unknown customer"
        )
        title = f"Service reminder: {item.name}"
        message = (
            f"{customer_name}'s {item.name}"
            f"{' (S/N: ' + item.serial_number + ')' if item.serial_number else ''}"
            f" is {status_text}.\n"
            f"Last serviced: {item.last_service_date.isoformat()}. "
            f"Service interval: {item.service_interval_days} days."
        )

        for admin_id in admin_ids:
            recent = Notification.query.filter(
                Notification.notification_type == "service_reminder",
                Notification.entity_type == "service_item",
                Notification.entity_id == item.id,
                Notification.user_id == admin_id,
                Notification.created_at >= recent_cutoff,
            ).first()
            if recent is not None:
                continue

            notification = _create_reminder_notification(
                item_id=item.id,
                admin_id=admin_id,
                run_date=today,
                title=title,
                message=message,
                severity=severity,
            )
            if notification is not None:
                notification_service._queue_email(notification)
                reminders_sent += 1

    logger.info("Service reminder check complete: %d reminders sent.", reminders_sent)
    return reminders_sent


def _create_reminder_notification(
    item_id,
    admin_id,
    run_date,
    title,
    message,
    severity,
):
    """Create a reminder notification after claiming the delivery slot."""
    try:
        delivery = ServiceReminderDelivery(
            service_item_id=item_id,
            user_id=admin_id,
            delivery_date=run_date,
        )
        notification = Notification(
            user_id=admin_id,
            notification_type="service_reminder",
            title=title,
            message=message,
            entity_type="service_item",
            entity_id=item_id,
            severity=severity,
        )
        db.session.add(delivery)
        db.session.add(notification)
        db.session.commit()
        return notification
    except IntegrityError:
        db.session.rollback()
        return None
