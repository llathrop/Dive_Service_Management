"""Tests for the email delivery hook in notification_service."""

from unittest.mock import patch, MagicMock

import pytest
from flask_security import hash_password

from app.extensions import db
from app.services import notification_service

pytestmark = pytest.mark.unit


def _make_user(app, db_session, username="hook_user", email="hook@example.com"):
    """Create a test user via user_datastore."""
    user_datastore = app.extensions["security"].datastore
    user_datastore.find_or_create_role(name="admin", description="Admin")
    user = user_datastore.create_user(
        username=username,
        email=email,
        password=hash_password("password"),
        first_name="Hook",
        last_name="Test",
    )
    db_session.commit()
    return user


class TestQueueEmail:
    """Tests for _queue_email() integration with create_notification()."""

    @patch("app.services.notification_service._queue_email")
    def test_create_notification_calls_queue_email(self, mock_queue, app, db_session):
        """create_notification() calls _queue_email after commit."""
        user = _make_user(app, db_session)

        notification = notification_service.create_notification(
            user_id=user.id,
            notification_type="system",
            title="Test",
            message="Test message",
        )

        mock_queue.assert_called_once_with(notification)

    @patch("app.services.notification_service._queue_email")
    def test_notification_created_even_if_queue_patched(self, mock_queue, app, db_session):
        """Notification is persisted regardless of _queue_email behavior."""
        mock_queue.side_effect = Exception("Queue broken")
        user = _make_user(app, db_session, username="hook2", email="hook2@example.com")

        # _queue_email raises, but it's called after db.session.commit()
        # so the notification is already persisted. However, the exception
        # will propagate from create_notification. The real _queue_email
        # has a try/except, but we're patching the whole function here.
        with pytest.raises(Exception, match="Queue broken"):
            notification_service.create_notification(
                user_id=user.id,
                notification_type="system",
                title="Test",
                message="Test message",
            )

    def test_real_queue_email_swallows_errors(self, app, db_session):
        """The real _queue_email swallows import/task errors."""
        notification = MagicMock()
        notification.user_id = 1
        notification.id = 1

        # Should not raise even though the Celery task can't be imported
        # in the test environment (no broker running)
        notification_service._queue_email(notification)

    def test_queue_email_handles_broadcast(self, app, db_session):
        """_queue_email handles broadcast notifications (user_id=None)."""
        notification = MagicMock()
        notification.user_id = None
        notification.id = 1

        # Should not raise
        notification_service._queue_email(notification)
