"""Blueprint tests for service item customer relationship."""

import pytest

from app.extensions import db as _db
from app.models.service_item import ServiceItem
from tests.factories import (
    BaseFactory,
    CustomerFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
)

pytestmark = pytest.mark.blueprint


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    for f in (BaseFactory, CustomerFactory, ServiceItemFactory,
              ServiceOrderFactory, ServiceOrderItemFactory):
        f._meta.sqlalchemy_session = db_session


class TestCreateItemWithoutCustomer:
    """POST to create an item without customer_id should fail."""

    def test_create_item_without_customer_error(self, logged_in_client, db_session):
        """Form submission without customer_id should re-render with errors."""
        resp = logged_in_client.post("/items/new", data={
            "name": "Test Regulator",
            "item_category": "Regulator",
        }, follow_redirects=True)
        assert resp.status_code == 200
        html = resp.data.decode()
        # Form should re-render (not redirect to detail) since validation failed
        assert "New Service Item" in html or "Save Item" in html


class TestItemDetailServiceHistory:
    """Verify service history appears on item detail page."""

    def test_item_detail_shows_service_history(self, logged_in_client, db_session):
        """Item detail should show linked service orders."""
        customer = CustomerFactory()
        item = ServiceItemFactory(customer=customer)
        order = ServiceOrderFactory(customer=customer)
        ServiceOrderItemFactory(order=order, service_item=item,
                                work_description="Full overhaul")
        db_session.commit()

        resp = logged_in_client.get(f"/items/{item.id}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Service History" in html
        assert order.order_number in html
        assert "Full overhaul" in html

    def test_item_detail_empty_service_history(self, logged_in_client, db_session):
        """Item detail should show empty state when no orders exist."""
        customer = CustomerFactory()
        item = ServiceItemFactory(customer=customer)
        db_session.commit()

        resp = logged_in_client.get(f"/items/{item.id}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "No service history on record." in html


class TestQuickCreateItemWithoutCustomer:
    """POST to quick-create without customer_id should return 400."""

    def test_quick_create_item_without_customer_400(self, logged_in_client, db_session):
        resp = logged_in_client.post("/items/quick-create", data={
            "name": "Test Item",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "Customer is required" in data["error"]


class TestEditItemCustomer:
    """Verify item customer can be changed or not removed."""

    def test_edit_item_change_customer(self, app, db_session):
        """Item can be reassigned to a different customer via update_item."""
        from app.services import item_service

        customer1 = CustomerFactory()
        customer2 = CustomerFactory()
        item = ServiceItemFactory(customer=customer1)
        db_session.commit()

        item_service.update_item(item.id, {"customer_id": customer2.id})

        updated = db_session.get(ServiceItem, item.id)
        assert updated.customer_id == customer2.id

    def test_edit_item_remove_customer_blocked(self, logged_in_client, db_session, app):
        """Customer cannot be set to empty on edit."""
        customer = CustomerFactory()
        item = ServiceItemFactory(customer=customer)
        db_session.commit()

        resp = logged_in_client.post(f"/items/{item.id}/edit", data={
            "name": item.name,
            "item_category": item.item_category or "",
            "serviceability": item.serviceability,
            # customer_id omitted
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Should stay on form (not redirect to detail) since validation fails
        html = resp.data.decode()
        assert "Save Item" in html

        with app.app_context():
            unchanged = ServiceItem.query.get(item.id)
            assert unchanged.customer_id == customer.id
