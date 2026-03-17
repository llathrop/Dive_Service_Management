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
from app.models.notification_read import NotificationRead
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


# =========================================================================
# Per-user broadcast read state (P0-2)
# =========================================================================


class TestBroadcastPerUserReadState:
    """Tests for per-user read tracking on broadcast notifications."""

    def test_broadcast_mark_read_is_per_user(self, app, db_session):
        """Marking a broadcast read for user A does not affect user B."""
        user_a = _make_admin_user(
            app, db_session, username="bcast_a", email="bcast_a@example.com"
        )
        user_b = _make_tech_user(
            app, db_session, username="bcast_b", email="bcast_b@example.com"
        )

        broadcast = notification_service.create_notification(
            user_id=None,
            notification_type="system",
            title="System-wide announcement",
            message="Broadcast body",
        )

        # User A marks the broadcast as read
        result = notification_service.mark_as_read(broadcast.id, user_id=user_a.id)
        assert result is not None

        # User A should see it as read (unread count = 0)
        assert notification_service.get_unread_count(user_a.id) == 0

        # User B should still see it as unread (unread count = 1)
        assert notification_service.get_unread_count(user_b.id) == 1

        # The Notification row itself should NOT have is_read flipped
        db_session.refresh(broadcast)
        assert broadcast.is_read is False

    def test_mark_all_read_handles_broadcasts_per_user(self, app, db_session):
        """mark_all_read for user A leaves broadcasts unread for user B."""
        user_a = _make_admin_user(
            app, db_session, username="mall_a", email="mall_a@example.com"
        )
        user_b = _make_tech_user(
            app, db_session, username="mall_b", email="mall_b@example.com"
        )

        # One direct notification for each user and one broadcast
        notification_service.create_notification(
            user_id=user_a.id,
            notification_type="system",
            title="Direct for A",
            message="msg",
        )
        notification_service.create_notification(
            user_id=user_b.id,
            notification_type="system",
            title="Direct for B",
            message="msg",
        )
        notification_service.create_notification(
            user_id=None,
            notification_type="system",
            title="Broadcast",
            message="msg",
        )

        # Before: A sees 2 unread (1 direct + 1 broadcast)
        assert notification_service.get_unread_count(user_a.id) == 2
        # Before: B sees 2 unread (1 direct + 1 broadcast)
        assert notification_service.get_unread_count(user_b.id) == 2

        # Mark all read for user A
        marked = notification_service.mark_all_read(user_a.id)
        assert marked == 2

        # A now sees 0 unread
        assert notification_service.get_unread_count(user_a.id) == 0

        # B still sees 2 unread — the broadcast and their own direct notification
        assert notification_service.get_unread_count(user_b.id) == 2

    def test_unread_count_includes_unread_broadcasts(self, app, db_session):
        """get_unread_count correctly sums direct + broadcast unread per user."""
        user_a = _make_admin_user(
            app, db_session, username="cnt_a", email="cnt_a@example.com"
        )
        user_b = _make_tech_user(
            app, db_session, username="cnt_b", email="cnt_b@example.com"
        )

        # 2 direct for A, 1 broadcast
        notification_service.create_notification(
            user_id=user_a.id,
            notification_type="system",
            title="Direct A-1",
            message="msg",
        )
        notification_service.create_notification(
            user_id=user_a.id,
            notification_type="system",
            title="Direct A-2",
            message="msg",
        )
        broadcast = notification_service.create_notification(
            user_id=None,
            notification_type="system",
            title="Broadcast",
            message="msg",
        )

        # A: 2 direct + 1 broadcast = 3
        assert notification_service.get_unread_count(user_a.id) == 3
        # B: 0 direct + 1 broadcast = 1
        assert notification_service.get_unread_count(user_b.id) == 1

        # Mark broadcast read for A only
        notification_service.mark_as_read(broadcast.id, user_id=user_a.id)

        # A: 2 direct + 0 broadcast = 2
        assert notification_service.get_unread_count(user_a.id) == 2
        # B: 0 direct + 1 broadcast = 1 (unchanged)
        assert notification_service.get_unread_count(user_b.id) == 1

    def test_get_notifications_annotates_direct_read_state(self, app, db_session):
        """get_notifications() sets is_read_by_user on direct notifications."""
        _set_session(db_session)
        user = _make_admin_user(
            app, db_session, username="ann_d", email="ann_d@example.com"
        )

        n = notification_service.create_notification(
            user_id=user.id,
            notification_type="system",
            title="Direct Annotated",
            message="msg",
        )

        # Before marking read
        page = notification_service.get_notifications(user.id)
        item = page.items[0]
        assert item.is_read_by_user is False
        assert item.read_at_by_user is None

        # After marking read
        notification_service.mark_as_read(n.id, user_id=user.id)
        page = notification_service.get_notifications(user.id)
        item = page.items[0]
        assert item.is_read_by_user is True
        assert item.read_at_by_user is not None

    def test_get_notifications_annotates_broadcast_read_state(self, app, db_session):
        """get_notifications() sets is_read_by_user correctly for broadcasts."""
        _set_session(db_session)
        user_a = _make_admin_user(
            app, db_session, username="ann_ba", email="ann_ba@example.com"
        )
        user_b = _make_tech_user(
            app, db_session, username="ann_bb", email="ann_bb@example.com"
        )

        broadcast = notification_service.create_notification(
            user_id=None,
            notification_type="system",
            title="Broadcast Annotated",
            message="msg",
        )

        # Both users see it as unread initially
        page_a = notification_service.get_notifications(user_a.id)
        page_b = notification_service.get_notifications(user_b.id)
        assert page_a.items[0].is_read_by_user is False
        assert page_b.items[0].is_read_by_user is False

        # User A marks broadcast as read
        notification_service.mark_as_read(broadcast.id, user_id=user_a.id)
        db_session.expire_all()  # Ensure fresh query results

        # User A sees it as read
        page_a = notification_service.get_notifications(user_a.id)
        assert page_a.items[0].is_read_by_user is True
        assert page_a.items[0].read_at_by_user is not None

        # User B still sees unread (separate call to avoid identity map
        # clobbering the transient attributes set by _annotate_read_state)
        page_b = notification_service.get_notifications(user_b.id)
        assert page_b.items[0].is_read_by_user is False
        assert page_b.items[0].read_at_by_user is None

    def test_broadcast_mark_read_idempotent(self, app, db_session):
        """Marking the same broadcast read twice does not create duplicate rows."""
        user = _make_admin_user(
            app, db_session, username="idem_u", email="idem_u@example.com"
        )

        broadcast = notification_service.create_notification(
            user_id=None,
            notification_type="system",
            title="Idempotent test",
            message="msg",
        )

        # Mark read twice
        notification_service.mark_as_read(broadcast.id, user_id=user.id)
        notification_service.mark_as_read(broadcast.id, user_id=user.id)

        # Should have exactly one NotificationRead row
        read_count = NotificationRead.query.filter_by(
            notification_id=broadcast.id,
            user_id=user.id,
        ).count()
        assert read_count == 1

        # Unread count should be 0
        assert notification_service.get_unread_count(user.id) == 0
