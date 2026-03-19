"""Tests for quick-create service item route on the items blueprint."""

import pytest

from app.models.service_item import ServiceItem
from tests.factories import (
    BaseFactory,
    CustomerFactory,
    ServiceOrderFactory,
)


QUICK_CREATE_URL = "/items/quick-create"


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    """Bind Factory Boy factories to the test database session."""
    BaseFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session
    ServiceOrderFactory._meta.sqlalchemy_session = db_session


@pytest.fixture()
def customer(db_session):
    """Create a customer for quick-create tests."""
    c = CustomerFactory()
    db_session.commit()
    return c


class TestQuickCreateItemSuccess:
    """POST /items/quick-create creates a service item and returns JSON."""

    def test_quick_create_item_success(self, admin_client, app, db_session, customer):
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Apeks XTX50",
            "item_category": "Regulator",
            "serial_number": "REG-001",
            "brand": "Apeks",
            "model": "XTX50",
            "customer_id": customer.id,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "id" in data
        assert data["display_text"] == "Apeks XTX50 (REG-001)"

        with app.app_context():
            item = ServiceItem.query.get(data["id"])
            assert item is not None
            assert item.name == "Apeks XTX50"
            assert item.item_category == "Regulator"
            assert item.serial_number == "REG-001"
            assert item.brand == "Apeks"
            assert item.model == "XTX50"

    def test_quick_create_item_technician(self, logged_in_client, db_session, customer):
        """Technician role can also quick-create service items."""
        resp = logged_in_client.post(QUICK_CREATE_URL, data={
            "name": "Suunto D5",
            "item_category": "Computer",
            "customer_id": customer.id,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["display_text"] == "Suunto D5"

    def test_quick_create_item_minimal(self, admin_client, db_session, customer):
        """Name and customer_id are required; all other fields are optional."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Mystery Gear",
            "customer_id": customer.id,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["display_text"] == "Mystery Gear"

    def test_quick_create_item_with_customer(self, admin_client, app, db_session, customer):
        """Customer ID is passed through to the new service item."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Customer BCD",
            "item_category": "BCD",
            "customer_id": customer.id,
        })
        assert resp.status_code == 201
        data = resp.get_json()

        with app.app_context():
            item = ServiceItem.query.get(data["id"])
            assert item.customer_id == customer.id


class TestQuickCreateItemAuth:
    """Authentication and authorization checks."""

    def test_quick_create_item_requires_auth(self, client):
        resp = client.post(QUICK_CREATE_URL, data={"name": "NoAuth"})
        assert resp.status_code in (302, 403)

    def test_quick_create_item_requires_role(self, viewer_client):
        resp = viewer_client.post(QUICK_CREATE_URL, data={"name": "NoRole"})
        assert resp.status_code == 403


class TestQuickCreateItemValidation:
    """Validation error cases."""

    def test_quick_create_item_missing_name(self, admin_client):
        """Missing name returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "item_category": "Regulator",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "name" in data["error"].lower()

    def test_quick_create_item_missing_customer(self, admin_client):
        """Missing customer_id returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "No Customer Item",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "Customer is required" in data["error"]

    def test_quick_create_item_invalid_category(self, admin_client, db_session, customer):
        """Invalid category returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Bad Category Item",
            "item_category": "Spaceship",
            "customer_id": customer.id,
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "category" in data["error"].lower()

    def test_quick_create_item_duplicate_serial(self, admin_client, db_session, customer):
        """Duplicate serial number returns 409."""
        resp1 = admin_client.post(QUICK_CREATE_URL, data={
            "name": "First Item",
            "serial_number": "DUPE-001",
            "customer_id": customer.id,
        })
        assert resp1.status_code == 201

        resp2 = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Second Item",
            "serial_number": "DUPE-001",
            "customer_id": customer.id,
        })
        assert resp2.status_code == 409
        data = resp2.get_json()
        assert "error" in data
        assert "serial number" in data["error"].lower()


class TestOrderDetailDropdown:
    """Verify the order detail page includes the Create New option."""

    def test_detail_page_has_create_new_option(self, admin_client, db_session):
        """The service item dropdown has a '+ Create New Service Item' option."""
        order = ServiceOrderFactory()
        db_session.commit()

        resp = admin_client.get(f"/orders/{order.id}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "+ Create New Service Item" in html
        assert "__new__" in html
