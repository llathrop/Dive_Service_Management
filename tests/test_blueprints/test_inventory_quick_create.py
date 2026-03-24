"""Tests for quick-create inventory item route on the inventory blueprint."""

import pytest

from app.models.inventory import InventoryItem
from tests.factories import (
    BaseFactory,
    CustomerFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
)

pytestmark = pytest.mark.blueprint


QUICK_CREATE_URL = "/inventory/quick-create"


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    """Bind Factory Boy factories to the test database session."""
    BaseFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session
    ServiceItemFactory._meta.sqlalchemy_session = db_session
    ServiceOrderFactory._meta.sqlalchemy_session = db_session
    ServiceOrderItemFactory._meta.sqlalchemy_session = db_session


class TestQuickCreateInventorySuccess:
    """POST /inventory/quick-create creates an inventory item and returns JSON."""

    def test_create_success(self, admin_client, app):
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Viton O-Ring",
            "sku": "VOR-001",
            "category": "Parts",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "id" in data
        assert data["display_text"] == "Viton O-Ring (SKU: VOR-001)"

        with app.app_context():
            item = InventoryItem.query.get(data["id"])
            assert item is not None
            assert item.name == "Viton O-Ring"
            assert item.sku == "VOR-001"
            assert item.category == "Parts"

    def test_create_success_technician(self, logged_in_client):
        """Technician role can also quick-create inventory items."""
        resp = logged_in_client.post(QUICK_CREATE_URL, data={
            "name": "Silicone Grease",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["display_text"] == "Silicone Grease"

    def test_create_minimal(self, admin_client):
        """Only name is required; all other fields are optional."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Misc Part",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["display_text"] == "Misc Part"

    def test_with_optional_fields(self, admin_client, app):
        """SKU, category, and unit cost are stored when provided."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "HP Seat",
            "sku": "HPS-100",
            "category": "Reg Parts",
            "unit_cost": "3.50",
            "quantity_in_stock": "25",
            "reorder_level": "10",
        })
        assert resp.status_code == 201
        data = resp.get_json()

        with app.app_context():
            item = InventoryItem.query.get(data["id"])
            assert item.sku == "HPS-100"
            assert item.category == "Reg Parts"
            assert float(item.purchase_cost) == 3.5
            assert float(item.quantity_in_stock) == 25.0
            assert float(item.reorder_level) == 10.0


class TestQuickCreateInventoryAuth:
    """Authentication and authorization checks."""

    def test_requires_login(self, client):
        resp = client.post(QUICK_CREATE_URL, data={"name": "NoAuth"})
        assert resp.status_code in (302, 401)

    def test_requires_tech_or_admin(self, viewer_client):
        resp = viewer_client.post(QUICK_CREATE_URL, data={"name": "NoRole"})
        assert resp.status_code == 403


class TestQuickCreateInventoryValidation:
    """Validation error cases."""

    def test_name_required(self, admin_client):
        """Missing name returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "sku": "NO-NAME",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "name" in data["error"].lower()

    def test_name_too_long(self, admin_client):
        """Name exceeding 255 chars returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "X" * 256,
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_negative_unit_cost(self, admin_client):
        """Negative unit cost returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Neg Cost Part",
            "unit_cost": "-5.00",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_negative_quantity(self, admin_client):
        """Negative quantity returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Neg Qty Part",
            "quantity_in_stock": "-1",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_non_numeric_cost(self, admin_client):
        """Non-numeric unit cost returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Bad Cost Part",
            "unit_cost": "abc",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_duplicate_sku(self, admin_client):
        """Duplicate SKU returns 409."""
        resp1 = admin_client.post(QUICK_CREATE_URL, data={
            "name": "First Part",
            "sku": "DUPE-SKU",
        })
        assert resp1.status_code == 201

        resp2 = admin_client.post(QUICK_CREATE_URL, data={
            "name": "Second Part",
            "sku": "DUPE-SKU",
        })
        assert resp2.status_code == 409
        data = resp2.get_json()
        assert "error" in data
        assert "sku" in data["error"].lower()


class TestOrderDetailInventoryDropdown:
    """Verify the order detail page includes the Create New option."""

    def test_detail_page_has_create_new_inventory_option(
        self, admin_client, db_session
    ):
        """The inventory item dropdown has a '+ Create New Inventory Item' option."""
        order_item = ServiceOrderItemFactory()
        db_session.commit()
        order = order_item.order

        resp = admin_client.get(f"/orders/{order.id}")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "+ Create New Inventory Item" in html
        assert "__new__" in html
