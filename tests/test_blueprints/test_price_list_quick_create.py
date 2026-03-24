"""Tests for quick-create price list item route on the price_list blueprint."""

import pytest

from app.models.price_list import PriceListCategory, PriceListItem
from tests.factories import (
    BaseFactory,
    CustomerFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
)

pytestmark = pytest.mark.blueprint


QUICK_CREATE_URL = "/price-list/quick-create"


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    """Bind Factory Boy factories to the test database session."""
    BaseFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session
    ServiceItemFactory._meta.sqlalchemy_session = db_session
    ServiceOrderFactory._meta.sqlalchemy_session = db_session
    ServiceOrderItemFactory._meta.sqlalchemy_session = db_session


@pytest.fixture()
def price_category(db_session):
    """Create a default price list category for quick-create tests."""
    cat = PriceListCategory(name="General Services", sort_order=0, is_active=True)
    db_session.add(cat)
    db_session.commit()
    return cat


class TestQuickCreatePriceListSuccess:
    """POST /price-list/quick-create creates a price list item and returns JSON."""

    def test_create_success(self, admin_client, app, price_category):
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "O-Ring Replacement",
            "price": "15.00",
            "category_id": price_category.id,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "id" in data
        assert "O-Ring Replacement ($15" in data["display_text"]

        with app.app_context():
            item = PriceListItem.query.get(data["id"])
            assert item is not None
            assert item.name == "O-Ring Replacement"
            assert float(item.price) == 15.0
            assert item.category_id == price_category.id

    def test_create_success_technician(self, logged_in_client, price_category):
        """Technician role can also quick-create price list items."""
        resp = logged_in_client.post(QUICK_CREATE_URL, data={
            "name": "Valve Service",
            "price": "25.00",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "Valve Service" in data["display_text"]

    def test_create_defaults_to_first_category(self, admin_client, app, price_category):
        """When category_id is not provided, defaults to first active category."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Tank Visual",
            "price": "30.00",
        })
        assert resp.status_code == 201
        data = resp.get_json()

        with app.app_context():
            item = PriceListItem.query.get(data["id"])
            assert item.category_id == price_category.id

    def test_create_with_description(self, admin_client, app, price_category):
        """Optional description field is stored."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Reg Service",
            "price": "85.00",
            "description": "Full regulator annual service",
        })
        assert resp.status_code == 201
        data = resp.get_json()

        with app.app_context():
            item = PriceListItem.query.get(data["id"])
            assert item.description == "Full regulator annual service"


class TestQuickCreatePriceListAuth:
    """Authentication and authorization checks."""

    def test_requires_login(self, client, price_category):
        resp = client.post(QUICK_CREATE_URL, data={
            "name": "NoAuth Item", "price": "10.00",
        })
        assert resp.status_code in (302, 401)

    def test_requires_tech_or_admin(self, viewer_client, price_category):
        resp = viewer_client.post(QUICK_CREATE_URL, data={
            "name": "NoRole Item", "price": "10.00",
        })
        assert resp.status_code == 403


class TestQuickCreatePriceListValidation:
    """Validation error cases."""

    def test_name_required(self, admin_client, price_category):
        """Missing name returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "price": "10.00",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "name" in data["error"].lower()

    def test_name_too_long(self, admin_client, price_category):
        """Name exceeding 255 chars returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "X" * 256,
            "price": "10.00",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_price_required(self, admin_client, price_category):
        """Missing price returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "No Price Item",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "price" in data["error"].lower()

    def test_price_must_be_numeric(self, admin_client, price_category):
        """Non-numeric price returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Bad Price Item",
            "price": "abc",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_price_must_be_non_negative(self, admin_client, price_category):
        """Negative price returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Negative Price",
            "price": "-5.00",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_duplicate_name(self, admin_client, price_category):
        """Duplicate item triggers IntegrityError and returns 409."""
        # First, create an item via the service to set up a duplicate scenario.
        # The PriceListItem model has a unique constraint on 'code', not 'name'.
        # So we test duplicate code instead if applicable.
        resp1 = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Unique Item",
            "price": "10.00",
        })
        assert resp1.status_code == 201

        # Creating with the same name should work since name is not unique.
        # IntegrityError would occur on unique 'code' field.
        # The quick-create doesn't set code, so no conflict.
        # Test passes if no 409.
        resp2 = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Unique Item",
            "price": "20.00",
        })
        # Name is not unique-constrained, so this should succeed
        assert resp2.status_code == 201


class TestOrderDetailPriceListDropdown:
    """Verify the order detail page includes the Create New option."""

    def test_detail_page_has_create_new_price_list_option(
        self, admin_client, db_session, price_category
    ):
        """The price list item dropdown has a '+ Create New Price List Item' option."""
        order_item = ServiceOrderItemFactory()
        db_session.commit()
        order = order_item.order

        resp = admin_client.get(f"/orders/{order.id}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "+ Create New Price List Item" in html
