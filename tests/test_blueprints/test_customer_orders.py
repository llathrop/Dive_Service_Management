"""Blueprint tests for customer detail order lists."""

import pytest

from tests.factories import (
    BaseFactory,
    CustomerFactory,
    ServiceOrderFactory,
)

pytestmark = pytest.mark.blueprint


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    for f in (BaseFactory, CustomerFactory, ServiceOrderFactory):
        f._meta.sqlalchemy_session = db_session


class TestCustomerDetailOrders:
    """Verify order sections appear on customer detail page."""

    def test_customer_detail_shows_open_orders(self, logged_in_client, db_session):
        """Customer detail should show open orders section."""
        customer = CustomerFactory()
        order = ServiceOrderFactory(customer=customer, status="in_progress")
        db_session.commit()

        resp = logged_in_client.get(f"/customers/{customer.id}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Open Orders" in html
        assert order.order_number in html

    def test_customer_detail_shows_completed_orders(self, logged_in_client, db_session):
        """Customer detail should show completed orders section."""
        customer = CustomerFactory()
        order = ServiceOrderFactory(customer=customer, status="completed")
        db_session.commit()

        resp = logged_in_client.get(f"/customers/{customer.id}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Order History" in html
        assert order.order_number in html

    def test_customer_detail_no_orders(self, logged_in_client, db_session):
        """Customer detail should show empty state when no orders."""
        customer = CustomerFactory()
        db_session.commit()

        resp = logged_in_client.get(f"/customers/{customer.id}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "No open orders." in html
        assert "No completed orders." in html
