"""Unit tests for customer_service.get_customer_orders()."""

import pytest

from app.services import customer_service
from tests.factories import (
    BaseFactory,
    CustomerFactory,
    ServiceOrderFactory,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    for f in (BaseFactory, CustomerFactory, ServiceOrderFactory):
        f._meta.sqlalchemy_session = db_session


class TestGetCustomerOrders:
    """Tests for get_customer_orders()."""

    def test_get_customer_orders_all(self, app, db_session):
        """Returns all non-deleted orders for a customer."""
        customer = CustomerFactory()
        ServiceOrderFactory(customer=customer, status="intake")
        ServiceOrderFactory(customer=customer, status="completed")
        db_session.commit()

        orders = customer_service.get_customer_orders(customer.id)
        assert len(orders) == 2

    def test_get_customer_orders_active_only(self, app, db_session):
        """active_only=True returns only active-status orders."""
        customer = CustomerFactory()
        ServiceOrderFactory(customer=customer, status="intake")
        ServiceOrderFactory(customer=customer, status="in_progress")
        ServiceOrderFactory(customer=customer, status="completed")
        ServiceOrderFactory(customer=customer, status="picked_up")
        db_session.commit()

        orders = customer_service.get_customer_orders(customer.id, active_only=True)
        assert len(orders) == 2
        statuses = {o.status for o in orders}
        assert statuses == {"intake", "in_progress"}

    def test_get_customer_orders_completed_only(self, app, db_session):
        """active_only=False returns only completed/cancelled orders."""
        customer = CustomerFactory()
        ServiceOrderFactory(customer=customer, status="intake")
        ServiceOrderFactory(customer=customer, status="completed")
        ServiceOrderFactory(customer=customer, status="cancelled")
        db_session.commit()

        orders = customer_service.get_customer_orders(customer.id, active_only=False)
        assert len(orders) == 2
        statuses = {o.status for o in orders}
        assert statuses == {"completed", "cancelled"}
