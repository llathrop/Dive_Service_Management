"""Unit tests for the inventory service layer.

Tests cover paginated listing, search, filtering, CRUD operations,
stock adjustments, low-stock detection, and category listing.
"""

from decimal import Decimal

import pytest

from app.extensions import db
from app.models.inventory import InventoryItem
from app.services import inventory_service

pytestmark = pytest.mark.unit


def _make_inventory_item(db_session, **kwargs):
    """Create and persist an InventoryItem with sensible defaults."""
    defaults = {
        "name": "Test Part",
        "category": "General",
        "quantity_in_stock": 10,
        "reorder_level": 5,
    }
    defaults.update(kwargs)
    item = InventoryItem(**defaults)
    db_session.add(item)
    db_session.commit()
    return item


class TestGetInventoryItems:
    """Tests for get_inventory_items()."""

    def test_get_inventory_items_paginated(self, app, db_session):
        """Creating items and fetching returns paginated results."""
        _make_inventory_item(db_session, name="Part A")
        _make_inventory_item(db_session, name="Part B")
        _make_inventory_item(db_session, name="Part C")

        result = inventory_service.get_inventory_items(page=1, per_page=25)
        assert result.total == 3
        assert len(result.items) == 3

    def test_get_inventory_items_search(self, app, db_session):
        """Search by name returns only matching items."""
        _make_inventory_item(db_session, name="Latex Seal")
        _make_inventory_item(db_session, name="O-Ring Kit")

        result = inventory_service.get_inventory_items(search="Latex")
        assert result.total == 1
        assert result.items[0].name == "Latex Seal"

    def test_get_inventory_items_low_stock_filter(self, app, db_session):
        """Low stock filter returns only items at or below reorder level."""
        _make_inventory_item(
            db_session,
            name="Low Stock Item",
            quantity_in_stock=2,
            reorder_level=5,
        )
        _make_inventory_item(
            db_session,
            name="Plenty Item",
            quantity_in_stock=50,
            reorder_level=5,
        )

        result = inventory_service.get_inventory_items(low_stock_only=True)
        assert result.total == 1
        assert result.items[0].name == "Low Stock Item"


class TestCreateInventoryItem:
    """Tests for create_inventory_item()."""

    def test_create_inventory_item(self, app, db_session):
        """create_inventory_item() persists an item with all fields."""
        data = {
            "name": "New Widget",
            "category": "Widgets",
            "sku": "WDG-001",
            "quantity_in_stock": 20,
            "reorder_level": 5,
            "manufacturer": "WidgetCo",
            "purchase_cost": Decimal("10.00"),
            "resale_price": Decimal("25.00"),
        }
        item = inventory_service.create_inventory_item(data)

        assert item.id is not None
        assert item.name == "New Widget"
        assert item.sku == "WDG-001"
        assert item.quantity_in_stock == 20

        fetched = db_session.get(InventoryItem, item.id)
        assert fetched is not None
        assert fetched.manufacturer == "WidgetCo"


class TestUpdateInventoryItem:
    """Tests for update_inventory_item()."""

    def test_update_inventory_item(self, app, db_session):
        """update_inventory_item() updates fields correctly."""
        item = _make_inventory_item(db_session, name="Old Name")

        updated = inventory_service.update_inventory_item(
            item.id, {"name": "New Name", "category": "Updated"}
        )

        assert updated.name == "New Name"
        assert updated.category == "Updated"


class TestAdjustStock:
    """Tests for adjust_stock()."""

    def test_adjust_stock_positive(self, app, db_session):
        """Positive adjustment increases stock level."""
        item = _make_inventory_item(
            db_session, name="Stock Test", quantity_in_stock=10
        )

        updated = inventory_service.adjust_stock(
            item.id, 5, "Received shipment"
        )
        assert updated.quantity_in_stock == 15

    def test_adjust_stock_negative(self, app, db_session):
        """Negative adjustment decreases stock level."""
        item = _make_inventory_item(
            db_session, name="Stock Test", quantity_in_stock=10
        )

        updated = inventory_service.adjust_stock(
            item.id, -3, "Used in service"
        )
        assert updated.quantity_in_stock == 7

    def test_adjust_stock_negative_below_zero(self, app, db_session):
        """Adjustment that would result in negative stock raises ValueError."""
        item = _make_inventory_item(
            db_session, name="Stock Test", quantity_in_stock=5
        )

        with pytest.raises(ValueError, match="negative stock"):
            inventory_service.adjust_stock(item.id, -10, "Over-deduction")


class TestGetLowStockItems:
    """Tests for get_low_stock_items()."""

    def test_get_low_stock_items(self, app, db_session):
        """Returns items where quantity_in_stock <= reorder_level."""
        low = _make_inventory_item(
            db_session,
            name="Low Item",
            quantity_in_stock=2,
            reorder_level=5,
            is_active=True,
        )
        _make_inventory_item(
            db_session,
            name="Plenty Item",
            quantity_in_stock=50,
            reorder_level=5,
            is_active=True,
        )
        # Item with reorder_level=0 should not appear
        _make_inventory_item(
            db_session,
            name="No Reorder",
            quantity_in_stock=0,
            reorder_level=0,
            is_active=True,
        )

        results = inventory_service.get_low_stock_items()
        ids = [i.id for i in results]
        assert low.id in ids
        assert len(results) == 1


class TestGetCategories:
    """Tests for get_categories()."""

    def test_get_categories(self, app, db_session):
        """Returns distinct sorted category names."""
        _make_inventory_item(db_session, name="A", category="Seals")
        _make_inventory_item(db_session, name="B", category="Valves")
        _make_inventory_item(db_session, name="C", category="Seals")

        categories = inventory_service.get_categories()
        assert categories == ["Seals", "Valves"]
