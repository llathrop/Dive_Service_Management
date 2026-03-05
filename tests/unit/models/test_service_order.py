"""Unit tests for the ServiceOrder model.

Tests cover creation, defaults, validation constants, properties,
soft-delete, relationships, and representation.
"""

from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models.customer import Customer
from app.models.service_order import (
    COMPLETED_STATUSES,
    VALID_PRIORITIES,
    VALID_STATUSES,
    ServiceOrder,
)
from app.models.service_order_item import ServiceOrderItem
from app.models.user import User
from tests.factories import (
    CustomerFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
    UserFactory,
)

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Configure all factories to use the given session."""
    ServiceOrderFactory._meta.sqlalchemy_session = db_session
    ServiceOrderItemFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session
    ServiceItemFactory._meta.sqlalchemy_session = db_session
    UserFactory._meta.sqlalchemy_session = db_session


class TestServiceOrderCreation:
    """Tests for basic service order creation and persistence."""

    def test_create_service_order(self, app, db_session):
        """A service order persists all required fields correctly."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="John", last_name="Diver")
        order = ServiceOrderFactory(
            order_number="SO-2026-00001",
            customer=customer,
            status="intake",
            priority="normal",
            date_received=date(2026, 3, 1),
            description="Annual regulator service",
        )

        fetched = db_session.get(ServiceOrder, order.id)
        assert fetched is not None
        assert fetched.order_number == "SO-2026-00001"
        assert fetched.customer_id == customer.id
        assert fetched.status == "intake"
        assert fetched.priority == "normal"
        assert fetched.date_received == date(2026, 3, 1)
        assert fetched.description == "Annual regulator service"

    def test_order_defaults(self, app, db_session):
        """Default values are applied correctly on a minimal order."""
        _set_session(db_session)
        customer = CustomerFactory()
        order = ServiceOrder(
            order_number="SO-2026-00099",
            customer_id=customer.id,
            date_received=date.today(),
        )
        db_session.add(order)
        db_session.commit()

        fetched = db_session.get(ServiceOrder, order.id)
        assert fetched.status == "intake"
        assert fetched.priority == "normal"
        assert fetched.is_deleted is False


class TestServiceOrderConstants:
    """Tests for validation constants."""

    def test_valid_statuses(self, app):
        """VALID_STATUSES contains all expected workflow statuses."""
        expected = [
            "intake",
            "assessment",
            "awaiting_approval",
            "in_progress",
            "awaiting_parts",
            "completed",
            "ready_for_pickup",
            "picked_up",
            "cancelled",
        ]
        assert VALID_STATUSES == expected

    def test_valid_priorities(self, app):
        """VALID_PRIORITIES contains the expected priority levels."""
        expected = ["low", "normal", "high", "rush"]
        assert VALID_PRIORITIES == expected

    def test_completed_statuses(self, app):
        """COMPLETED_STATUSES contains statuses treated as finished."""
        expected = ["completed", "ready_for_pickup", "picked_up"]
        assert COMPLETED_STATUSES == expected


class TestServiceOrderProperties:
    """Tests for computed properties."""

    def test_display_status(self, app, db_session):
        """display_status converts underscored status to title case."""
        _set_session(db_session)
        order = ServiceOrderFactory(status="awaiting_approval")
        assert order.display_status == "Awaiting Approval"

    def test_display_status_simple(self, app, db_session):
        """display_status works for simple single-word statuses."""
        _set_session(db_session)
        order = ServiceOrderFactory(status="intake")
        assert order.display_status == "Intake"

    def test_is_overdue_when_past_promised_date(self, app, db_session):
        """An order is overdue when date_promised is in the past and not completed."""
        _set_session(db_session)
        order = ServiceOrderFactory(
            status="in_progress",
            date_promised=date.today() - timedelta(days=1),
        )
        assert order.is_overdue is True

    def test_is_not_overdue_when_completed(self, app, db_session):
        """A completed order is not overdue even with a past promised date."""
        _set_session(db_session)
        order = ServiceOrderFactory(
            status="completed",
            date_promised=date.today() - timedelta(days=1),
        )
        assert order.is_overdue is False

    def test_is_not_overdue_when_picked_up(self, app, db_session):
        """A picked-up order is not overdue even with a past promised date."""
        _set_session(db_session)
        order = ServiceOrderFactory(
            status="picked_up",
            date_promised=date.today() - timedelta(days=1),
        )
        assert order.is_overdue is False

    def test_is_not_overdue_when_no_promised_date(self, app, db_session):
        """An order without a promised date is not overdue."""
        _set_session(db_session)
        order = ServiceOrderFactory(
            status="in_progress",
            date_promised=None,
        )
        assert order.is_overdue is False

    def test_is_not_overdue_when_future_date(self, app, db_session):
        """An order with a future promised date is not overdue."""
        _set_session(db_session)
        order = ServiceOrderFactory(
            status="in_progress",
            date_promised=date.today() + timedelta(days=7),
        )
        assert order.is_overdue is False


class TestServiceOrderSoftDelete:
    """Tests for soft-delete functionality."""

    def test_soft_delete(self, app, db_session):
        """soft_delete() sets is_deleted and deleted_at."""
        _set_session(db_session)
        order = ServiceOrderFactory()
        order.soft_delete()
        db_session.commit()

        fetched = db_session.get(ServiceOrder, order.id)
        assert fetched.is_deleted is True
        assert fetched.deleted_at is not None

        # not_deleted() should exclude this order
        active = ServiceOrder.not_deleted().all()
        assert order.id not in [o.id for o in active]


class TestServiceOrderRelationships:
    """Tests for model relationships."""

    def test_customer_relationship(self, app, db_session):
        """An order links to its customer via the relationship."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Reef", last_name="Diver")
        order = ServiceOrderFactory(customer=customer)

        assert order.customer.id == customer.id
        assert order.customer.first_name == "Reef"

    def test_assigned_tech_relationship(self, app, db_session):
        """An order links to its assigned technician via the relationship."""
        _set_session(db_session)
        tech = UserFactory(first_name="Tech", last_name="Worker")
        order = ServiceOrderFactory(assigned_tech=tech)

        assert order.assigned_tech is not None
        assert order.assigned_tech.id == tech.id
        assert order.assigned_tech.first_name == "Tech"

    def test_order_items_relationship(self, app, db_session):
        """An order can have multiple order items."""
        _set_session(db_session)
        order = ServiceOrderFactory()
        item1 = ServiceOrderItemFactory(order=order)
        item2 = ServiceOrderItemFactory(order=order)

        items = order.order_items.all()
        assert len(items) == 2
        item_ids = {i.id for i in items}
        assert item1.id in item_ids
        assert item2.id in item_ids


class TestServiceOrderRepr:
    """Tests for __repr__."""

    def test_repr(self, app, db_session):
        """__repr__ includes id and order_number."""
        _set_session(db_session)
        order = ServiceOrderFactory(order_number="SO-2026-00042")
        expected = f"<ServiceOrder {order.id} 'SO-2026-00042'>"
        assert repr(order) == expected
