"""Unit tests for the notification service layer.

Tests cover creating notifications, querying with pagination, unread
counts, marking as read, and domain-specific notification helpers for
low stock, order status changes, and payment receipts.
"""

from datetime import date
from decimal import Decimal

import pytest
from flask_security import hash_password

from app.extensions import db
from app.models.inventory import InventoryItem
from app.models.invoice import Invoice
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.service_order import ServiceOrder
from app.services import notification_service
from tests.factories import NotificationFactory

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Configure all factories to use the given session."""
    NotificationFactory._meta.sqlalchemy_session = db_session


def _make_admin_user(app, db_session, username="admin_notif", email="admin_notif@example.com"):
    """Create an admin user using user_datastore."""
    user_datastore = app.extensions["security"].datastore
    admin_role = user_datastore.find_or_create_role(
        name="admin", description="Full system access"
    )
    user = user_datastore.create_user(
        username=username,
        email=email,
        password=hash_password("password"),
        first_name="Admin",
        last_name="User",
    )
    user_datastore.add_role_to_user(user, admin_role)
    db_session.commit()
    return user


def _make_tech_user(app, db_session, username="tech_notif", email="tech_notif@example.com"):
    """Create a technician user using user_datastore."""
    user_datastore = app.extensions["security"].datastore
    tech_role = user_datastore.find_or_create_role(
        name="technician", description="Create/edit data"
    )
    user = user_datastore.create_user(
        username=username,
        email=email,
        password=hash_password("password"),
        first_name="Tech",
        last_name="User",
    )
    user_datastore.add_role_to_user(user, tech_role)
    db_session.commit()
    return user


def _make_customer(db_session, **kwargs):
    """Create and persist a Customer with sensible defaults."""
    from app.models.customer import Customer
    defaults = {
        "customer_type": "individual",
        "first_name": "Test",
        "last_name": "Diver",
    }
    defaults.update(kwargs)
    customer = Customer(**defaults)
    db_session.add(customer)
    db_session.commit()
    return customer


# =========================================================================
# create_notification
# =========================================================================


class TestCreateNotification:
    """Tests for create_notification()."""

    def test_create_notification(self, app, db_session):
        """create_notification() persists a notification correctly."""
        admin = _make_admin_user(app, db_session)

        result = notification_service.create_notification(
            user_id=admin.id,
            notification_type="system",
            title="Test Title",
            message="Test message body",
            severity="info",
        )

        assert result.id is not None
        assert result.user_id == admin.id
        assert result.notification_type == "system"
        assert result.title == "Test Title"
        assert result.message == "Test message body"
        assert result.severity == "info"
        assert result.is_read is False


# =========================================================================
# get_notifications
# =========================================================================


class TestGetNotifications:
    """Tests for get_notifications()."""

    def test_get_notifications(self, app, db_session):
        """get_notifications() returns paginated notifications for a user."""
        _set_session(db_session)
        admin = _make_admin_user(app, db_session)

        # Create several notifications
        for i in range(5):
            notification_service.create_notification(
                user_id=admin.id,
                notification_type="system",
                title=f"Notification {i}",
                message=f"Message {i}",
            )

        result = notification_service.get_notifications(
            user_id=admin.id, page=1, per_page=3
        )

        assert result.total == 5
        assert len(result.items) == 3

    def test_get_notifications_includes_broadcast(self, app, db_session):
        """get_notifications() includes broadcast notifications (user_id=None)."""
        _set_session(db_session)
        admin = _make_admin_user(app, db_session)

        # Create a targeted notification
        notification_service.create_notification(
            user_id=admin.id,
            notification_type="system",
            title="Targeted",
            message="For admin",
        )
        # Create a broadcast notification
        notification_service.create_notification(
            user_id=None,
            notification_type="system",
            title="Broadcast",
            message="For everyone",
        )

        result = notification_service.get_notifications(
            user_id=admin.id, page=1, per_page=20
        )

        assert result.total == 2


# =========================================================================
# get_unread_count
# =========================================================================


class TestGetUnreadCount:
    """Tests for get_unread_count()."""

    def test_get_unread_count(self, app, db_session):
        """get_unread_count() returns the count of unread notifications."""
        _set_session(db_session)
        admin = _make_admin_user(app, db_session)

        notification_service.create_notification(
            user_id=admin.id,
            notification_type="system",
            title="Unread 1",
            message="Test",
        )
        notification_service.create_notification(
            user_id=admin.id,
            notification_type="system",
            title="Unread 2",
            message="Test",
        )

        count = notification_service.get_unread_count(admin.id)
        assert count == 2

    def test_get_unread_count_excludes_read(self, app, db_session):
        """get_unread_count() does not count read notifications."""
        _set_session(db_session)
        admin = _make_admin_user(app, db_session)

        n1 = notification_service.create_notification(
            user_id=admin.id,
            notification_type="system",
            title="To be read",
            message="Test",
        )
        notification_service.create_notification(
            user_id=admin.id,
            notification_type="system",
            title="Unread",
            message="Test",
        )

        # Mark one as read
        notification_service.mark_as_read(n1.id)

        count = notification_service.get_unread_count(admin.id)
        assert count == 1


# =========================================================================
# mark_as_read
# =========================================================================


class TestMarkAsRead:
    """Tests for mark_as_read()."""

    def test_mark_as_read(self, app, db_session):
        """mark_as_read() sets is_read=True and read_at."""
        _set_session(db_session)
        admin = _make_admin_user(app, db_session)

        notification = notification_service.create_notification(
            user_id=admin.id,
            notification_type="system",
            title="To Read",
            message="Test message",
        )

        result = notification_service.mark_as_read(notification.id)

        assert result is not None
        assert result.is_read is True
        assert result.read_at is not None

    def test_mark_as_read_nonexistent(self, app, db_session):
        """mark_as_read() returns None for a non-existent ID."""
        result = notification_service.mark_as_read(99999)
        assert result is None


# =========================================================================
# mark_all_read
# =========================================================================


class TestMarkAllRead:
    """Tests for mark_all_read()."""

    def test_mark_all_read(self, app, db_session):
        """mark_all_read() marks all unread notifications as read."""
        _set_session(db_session)
        admin = _make_admin_user(app, db_session)

        notification_service.create_notification(
            user_id=admin.id,
            notification_type="system",
            title="Notif 1",
            message="Test",
        )
        notification_service.create_notification(
            user_id=admin.id,
            notification_type="system",
            title="Notif 2",
            message="Test",
        )

        count = notification_service.mark_all_read(admin.id)
        assert count == 2

        unread = notification_service.get_unread_count(admin.id)
        assert unread == 0


# =========================================================================
# notify_low_stock
# =========================================================================


class TestNotifyLowStock:
    """Tests for notify_low_stock()."""

    def test_notify_low_stock(self, app, db_session):
        """notify_low_stock() creates notifications for admin users."""
        admin = _make_admin_user(app, db_session)

        item = InventoryItem(
            sku="SKU-LOW-01",
            name="Wrist Seal",
            category="Seals",
            purchase_cost=Decimal("8.00"),
            resale_price=Decimal("20.00"),
            quantity_in_stock=2,
            reorder_level=5,
            unit_of_measure="each",
            is_active=True,
        )
        db_session.add(item)
        db_session.commit()

        notifications = notification_service.notify_low_stock(item)

        assert len(notifications) >= 1
        notif = notifications[0]
        assert notif.user_id == admin.id
        assert notif.notification_type == "low_stock"
        assert notif.severity == "warning"
        assert "Wrist Seal" in notif.title

    def test_notify_low_stock_critical(self, app, db_session):
        """notify_low_stock() uses critical severity for zero stock."""
        admin = _make_admin_user(app, db_session)

        item = InventoryItem(
            sku="SKU-OOS-01",
            name="O-Ring",
            category="Seals",
            purchase_cost=Decimal("2.00"),
            resale_price=Decimal("5.00"),
            quantity_in_stock=0,
            reorder_level=5,
            unit_of_measure="each",
            is_active=True,
        )
        db_session.add(item)
        db_session.commit()

        notifications = notification_service.notify_low_stock(item)

        assert len(notifications) >= 1
        notif = notifications[0]
        assert notif.notification_type == "critical_stock"
        assert notif.severity == "critical"


# =========================================================================
# notify_order_status_change
# =========================================================================


class TestNotifyOrderStatusChange:
    """Tests for notify_order_status_change()."""

    def test_notify_order_status_change(self, app, db_session):
        """notify_order_status_change() creates notifications for admins."""
        admin = _make_admin_user(app, db_session)
        customer = _make_customer(db_session)

        order = ServiceOrder(
            order_number="SO-2026-90001",
            customer_id=customer.id,
            status="assessment",
            priority="normal",
            date_received=date.today(),
        )
        db_session.add(order)
        db_session.commit()

        notifications = notification_service.notify_order_status_change(
            order, "intake", "assessment"
        )

        assert len(notifications) >= 1
        notif = notifications[0]
        assert notif.notification_type == "order_status_change"
        assert "SO-2026-90001" in notif.title
        assert "Intake" in notif.message
        assert "Assessment" in notif.message


# =========================================================================
# notify_payment_received
# =========================================================================


class TestNotifyPaymentReceived:
    """Tests for notify_payment_received()."""

    def test_notify_payment_received(self, app, db_session):
        """notify_payment_received() creates notifications for admin users."""
        admin = _make_admin_user(app, db_session)
        customer = _make_customer(db_session)

        invoice = Invoice(
            invoice_number="INV-2026-90001",
            customer_id=customer.id,
            status="partially_paid",
            issue_date=date.today(),
            subtotal=Decimal("200.00"),
            total=Decimal("200.00"),
            balance_due=Decimal("100.00"),
            amount_paid=Decimal("100.00"),
        )
        db_session.add(invoice)
        db_session.commit()

        payment = Payment(
            invoice_id=invoice.id,
            payment_type="payment",
            amount=Decimal("100.00"),
            payment_date=date.today(),
            payment_method="credit_card",
        )
        db_session.add(payment)
        db_session.commit()

        notifications = notification_service.notify_payment_received(
            invoice, payment
        )

        assert len(notifications) >= 1
        notif = notifications[0]
        assert notif.notification_type == "payment_received"
        assert "INV-2026-90001" in notif.title
        assert "$100.00" in notif.message
