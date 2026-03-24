"""Unit tests for the Notification model.

Tests cover creation, defaults, validation constants, properties,
and the user relationship.
"""

import pytest
from flask_security import hash_password

from app.extensions import db
from app.models.notification import (
    VALID_NOTIFICATION_TYPES,
    VALID_SEVERITIES,
    Notification,
)
from tests.factories import NotificationFactory

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Configure all factories to use the given session."""
    NotificationFactory._meta.sqlalchemy_session = db_session


# =========================================================================
# Notification creation
# =========================================================================


class TestNotificationCreation:
    """Tests for basic notification creation and persistence."""

    def test_create_notification(self, app, db_session):
        """A notification persists all required fields correctly."""
        _set_session(db_session)
        notification = NotificationFactory(
            notification_type="system",
            title="Test Notification",
            message="This is a test notification.",
            severity="info",
        )

        fetched = db_session.get(Notification, notification.id)
        assert fetched is not None
        assert fetched.notification_type == "system"
        assert fetched.title == "Test Notification"
        assert fetched.message == "This is a test notification."
        assert fetched.severity == "info"

    def test_notification_is_read_defaults_false(self, app, db_session):
        """is_read defaults to False for new notifications."""
        _set_session(db_session)
        notification = NotificationFactory()

        fetched = db_session.get(Notification, notification.id)
        assert fetched.is_read is False

    def test_notification_read_at_defaults_none(self, app, db_session):
        """read_at defaults to None for new notifications."""
        _set_session(db_session)
        notification = NotificationFactory()

        fetched = db_session.get(Notification, notification.id)
        assert fetched.read_at is None


# =========================================================================
# Notification constants
# =========================================================================


class TestNotificationConstants:
    """Tests for validation constants."""

    def test_valid_severities(self, app):
        """VALID_SEVERITIES contains all expected severity levels."""
        expected = ["info", "warning", "critical"]
        assert VALID_SEVERITIES == expected

    def test_valid_notification_types(self, app):
        """VALID_NOTIFICATION_TYPES contains all expected notification types."""
        expected = [
            "low_stock",
            "critical_stock",
            "overdue_invoice",
            "order_status_change",
            "order_approaching_due",
            "order_overdue",
            "order_assigned",
            "serviceability_change",
            "payment_received",
            "service_reminder",
            "system",
        ]
        assert VALID_NOTIFICATION_TYPES == expected


# =========================================================================
# Notification properties
# =========================================================================


class TestNotificationProperties:
    """Tests for computed properties."""

    def test_display_severity_info(self, app, db_session):
        """display_severity returns title-cased severity."""
        _set_session(db_session)
        notification = NotificationFactory(severity="info")
        assert notification.display_severity == "Info"

    def test_display_severity_warning(self, app, db_session):
        """display_severity returns title-cased severity for warning."""
        _set_session(db_session)
        notification = NotificationFactory(severity="warning")
        assert notification.display_severity == "Warning"

    def test_display_severity_critical(self, app, db_session):
        """display_severity returns title-cased severity for critical."""
        _set_session(db_session)
        notification = NotificationFactory(severity="critical")
        assert notification.display_severity == "Critical"


# =========================================================================
# Notification relationships
# =========================================================================


class TestNotificationRelationships:
    """Tests for model relationships."""

    def test_user_relationship(self, app, db_session):
        """A notification links to its user via the relationship."""
        _set_session(db_session)
        with app.app_context():
            user_datastore = app.extensions["security"].datastore
            role = user_datastore.find_or_create_role(
                name="technician", description="Create/edit data"
            )
            user = user_datastore.create_user(
                username="notif_user",
                email="notif_user@example.com",
                password=hash_password("password"),
                first_name="Notif",
                last_name="User",
            )
            user_datastore.add_role_to_user(user, role)
            db_session.commit()

            notification = NotificationFactory(user_id=user.id)

            assert notification.user is not None
            assert notification.user.id == user.id
            assert notification.user.username == "notif_user"

    def test_broadcast_notification_has_no_user(self, app, db_session):
        """A broadcast notification (user_id=None) has no user."""
        _set_session(db_session)
        notification = NotificationFactory(user_id=None)

        assert notification.user is None


# =========================================================================
# Notification __repr__
# =========================================================================


class TestNotificationRepr:
    """Tests for __repr__."""

    def test_repr(self, app, db_session):
        """__repr__ includes id and notification_type."""
        _set_session(db_session)
        notification = NotificationFactory(notification_type="low_stock")
        expected = f"<Notification {notification.id} type='low_stock'>"
        assert repr(notification) == expected
