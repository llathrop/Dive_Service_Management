"""Tests for recurring service reminders."""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.notification import Notification
from app.models.service_reminder_delivery import ServiceReminderDelivery
from app.services import notification_service
from app.services.service_reminder_service import check_service_reminders
from tests.factories import BaseFactory, CustomerFactory, ServiceItemFactory

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    for f in (BaseFactory, CustomerFactory, ServiceItemFactory):
        f._meta.sqlalchemy_session = db_session


@pytest.fixture(autouse=True)
def _disable_email_queue(monkeypatch):
    """Keep reminder tests on the pytest app/db instead of Celery/email."""
    monkeypatch.setattr(
        notification_service,
        "_queue_email",
        lambda notification: None,
    )


def _create_admin_user(
    app,
    db_session,
    username="reminderadmin",
    email="reminderadmin@example.com",
    active=True,
):
    """Create an admin user so reminders have someone to notify."""
    from flask_security import hash_password

    user_datastore = app.extensions["security"].datastore
    admin_role = user_datastore.find_or_create_role(
        name="admin", description="Full system access"
    )
    user = user_datastore.create_user(
        username=username,
        email=email,
        password=hash_password("password"),
        first_name="Reminder",
        last_name="Admin",
    )
    user.active = active
    user_datastore.add_role_to_user(user, admin_role)
    db_session.commit()
    return user


@pytest.fixture()
def _create_admin(app, db_session):
    return _create_admin_user(app, db_session)


class TestServiceReminders:
    """Tests for check_service_reminders task."""

    def test_reminder_sent_when_due(self, app, db_session, _create_admin):
        """Item with last_service_date 330 days ago and 365-day interval
        should trigger a reminder (due within 30 days)."""
        customer = CustomerFactory()
        ServiceItemFactory(
            customer=customer,
            last_service_date=date.today() - timedelta(days=340),
            service_interval_days=365,
        )
        db_session.commit()

        count = check_service_reminders()

        assert count == 1
        notification = Notification.query.filter_by(
            notification_type="service_reminder"
        ).first()
        assert notification is not None
        assert "Service reminder" in notification.title
        assert customer.display_name in notification.message
        assert notification.user_id == _create_admin.id

    def test_no_reminder_when_not_due(self, app, db_session, _create_admin):
        """Item serviced 100 days ago with 365-day interval should not
        trigger a reminder (not due within 30 days)."""
        ServiceItemFactory(
            last_service_date=date.today() - timedelta(days=100),
            service_interval_days=365,
        )
        db_session.commit()

        count = check_service_reminders()

        assert count == 0
        assert Notification.query.filter_by(
            notification_type="service_reminder"
        ).count() == 0

    def test_inactive_admin_is_not_notified(self, app, db_session):
        """Disabled admins should not receive service reminders."""
        active_admin = _create_admin_user(
            app,
            db_session,
            username="active-admin",
            email="active-admin@example.com",
            active=True,
        )
        _create_admin_user(
            app,
            db_session,
            username="inactive-admin",
            email="inactive-admin@example.com",
            active=False,
        )

        item = ServiceItemFactory(
            last_service_date=date.today() - timedelta(days=340),
            service_interval_days=365,
        )
        db_session.commit()

        count = check_service_reminders()

        assert count == 1
        notif = Notification.query.filter_by(
            notification_type="service_reminder",
            entity_type="service_item",
            entity_id=item.id,
        ).one()
        assert notif.user_id == active_admin.id
        assert (
            Notification.query.filter_by(
                notification_type="service_reminder",
                entity_type="service_item",
                entity_id=item.id,
                user_id=active_admin.id,
            ).count()
            == 1
        )
        assert (
            Notification.query.filter_by(
                notification_type="service_reminder",
                entity_type="service_item",
                entity_id=item.id,
                user_id=None,
            ).count()
            == 0
        )

    def test_recent_reminder_for_one_admin_does_not_suppress_others(
        self, app, db_session
    ):
        """A reminder already sent to one admin should not block another."""
        admin_a = _create_admin_user(
            app,
            db_session,
            username="reminderadmin-a",
            email="reminderadmin-a@example.com",
        )
        admin_b = _create_admin_user(
            app,
            db_session,
            username="reminderadmin-b",
            email="reminderadmin-b@example.com",
        )

        item = ServiceItemFactory(
            last_service_date=date.today() - timedelta(days=340),
            service_interval_days=365,
        )
        db_session.add(
            Notification(
                user_id=admin_a.id,
                notification_type="service_reminder",
                title="Existing reminder",
                message="Already reminded",
                entity_type="service_item",
                entity_id=item.id,
                severity="info",
                created_at=datetime.now(timezone.utc) - timedelta(days=5),
            )
        )
        db_session.commit()

        count = check_service_reminders()

        assert count == 1
        assert (
            Notification.query.filter_by(
                notification_type="service_reminder",
                entity_type="service_item",
                entity_id=item.id,
                user_id=admin_a.id,
            ).count()
            == 1
        )
        assert (
            Notification.query.filter_by(
                notification_type="service_reminder",
                entity_type="service_item",
                entity_id=item.id,
                user_id=admin_b.id,
            ).count()
            == 1
        )

    def test_existing_delivery_guard_blocks_duplicate_send(
        self, app, db_session, _create_admin
    ):
        """A claimed delivery slot should prevent a second send."""
        item = ServiceItemFactory(
            last_service_date=date.today() - timedelta(days=340),
            service_interval_days=365,
        )
        db_session.add(
            ServiceReminderDelivery(
                service_item_id=item.id,
                user_id=_create_admin.id,
                delivery_date=date.today(),
            )
        )
        db_session.commit()

        count = check_service_reminders()

        assert count == 0
        assert (
            Notification.query.filter_by(
                notification_type="service_reminder",
                entity_type="service_item",
                entity_id=item.id,
                user_id=_create_admin.id,
            ).count()
            == 0
        )

    def test_no_reminder_without_interval(self, app, db_session, _create_admin):
        """Item with no service_interval_days should not trigger a reminder."""
        ServiceItemFactory(
            last_service_date=date.today() - timedelta(days=400),
            service_interval_days=None,
        )
        db_session.commit()

        count = check_service_reminders()

        assert count == 0

    def test_no_reminder_without_last_service_date(self, app, db_session, _create_admin):
        """Item with interval but no last_service_date should not trigger
        a reminder."""
        ServiceItemFactory(
            last_service_date=None,
            service_interval_days=365,
        )
        db_session.commit()

        count = check_service_reminders()

        assert count == 0

    def test_no_duplicate_reminder(self, app, db_session, _create_admin):
        """Item that already has a recent reminder should not get another."""
        item = ServiceItemFactory(
            last_service_date=date.today() - timedelta(days=340),
            service_interval_days=365,
        )
        db_session.commit()

        # First run should create a reminder
        count1 = check_service_reminders()
        assert count1 == 1

        # Second run should skip (reminder already exists within 30 days)
        count2 = check_service_reminders()
        assert count2 == 0

        # Only one reminder notification total
        assert Notification.query.filter_by(
            notification_type="service_reminder",
            entity_type="service_item",
            entity_id=item.id,
        ).count() == 1

    def test_overdue_item_gets_reminder(self, app, db_session, _create_admin):
        """Item 400 days past service with 365-day interval should get a
        warning-severity reminder."""
        ServiceItemFactory(
            last_service_date=date.today() - timedelta(days=400),
            service_interval_days=365,
        )
        db_session.commit()

        count = check_service_reminders()

        assert count == 1
        notification = Notification.query.filter_by(
            notification_type="service_reminder"
        ).first()
        assert notification is not None
        assert notification.severity == "warning"
        assert "overdue" in notification.message

    def test_soft_deleted_item_skipped(self, app, db_session, _create_admin):
        """Soft-deleted items should not trigger reminders."""
        item = ServiceItemFactory(
            last_service_date=date.today() - timedelta(days=400),
            service_interval_days=365,
        )
        item.soft_delete()
        db_session.commit()

        count = check_service_reminders()

        assert count == 0


class TestServiceIntervalDetailPage:
    """Tests for service interval display on item detail page."""

    def test_service_interval_on_detail_page(self, logged_in_client, db_session):
        """Item detail page should show next service due date."""
        for f in (BaseFactory, CustomerFactory, ServiceItemFactory):
            f._meta.sqlalchemy_session = db_session

        item = ServiceItemFactory(
            last_service_date=date.today() - timedelta(days=300),
            service_interval_days=365,
        )
        db_session.commit()

        resp = logged_in_client.get(f"/items/{item.id}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Service Interval" in html
        assert "365 days" in html
        assert "Next Service Due" in html


class TestServiceIntervalForm:
    """Tests for the service_interval_days form field."""

    def test_service_interval_form_field(self, logged_in_client, db_session):
        """Form should save service_interval_days correctly."""
        for f in (BaseFactory, CustomerFactory, ServiceItemFactory):
            f._meta.sqlalchemy_session = db_session

        from app.models.service_item import ServiceItem

        customer = CustomerFactory()
        db_session.commit()

        resp = logged_in_client.post("/items/new", data={
            "name": "Test Regulator",
            "item_category": "Regulator",
            "serviceability": "serviceable",
            "customer_id": customer.id,
            "service_interval_days": 365,
        }, follow_redirects=True)
        assert resp.status_code == 200

        item = ServiceItem.query.filter_by(name="Test Regulator").first()
        assert item is not None
        assert item.service_interval_days == 365
