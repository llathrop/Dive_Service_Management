"""Celery tasks for asynchronous email delivery.

These tasks run in the worker container with Flask app context
provided by the ContextTask wrapper in celery_app.py.
"""

import logging

from app.celery_app import celery
from app.extensions import db

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_email_task(self, user_id, notification_id):
    """Send an email notification asynchronously.

    Args:
        user_id: ID of the recipient user.
        notification_id: ID of the notification to email.
    """
    from app.models.notification import Notification
    from app.models.user import User
    from app.services import email_service

    user = db.session.get(User, user_id)
    if user is None or not user.email:
        logger.warning("Email task skipped — user %s not found or has no email.", user_id)
        return

    notification = db.session.get(Notification, notification_id)
    if notification is None:
        logger.warning("Email task skipped — notification %s not found.", notification_id)
        return

    try:
        email_service.send_notification_email(user, notification)
    except Exception as exc:
        logger.error("Email task failed for user %s: %s", user_id, exc)
        raise self.retry(exc=exc)
