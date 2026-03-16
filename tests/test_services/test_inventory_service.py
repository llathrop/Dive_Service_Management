"""Tests for the inventory service layer."""

from decimal import Decimal

import pytest
from werkzeug.exceptions import NotFound

from app.services import inventory_service
from tests.factories import InventoryItemFactory


class TestGetInventoryItems:
    """Tests for inventory_service.get_inventory_items()."""

    def test_returns_paginated_results(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        InventoryItemFactory.create_batch(3)

        result = inventory_service.get_inventory_items(page=1, per_page=25)
        assert result.total == 3

    def test_search_filters_by_name(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        InventoryItemFactory(name="Latex Neck Seal")
        InventoryItemFactory(name="O-Ring Kit")

        result = inventory_service.get_inventory_items(search="Latex")
        assert result.total == 1
        assert result.items[0].name == "Latex Neck Seal"

    def test_search_filters_by_sku(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        InventoryItemFactory(sku="UNIQUE-SKU-001", name="Item A")
        InventoryItemFactory(sku="OTHER-SKU-002", name="Item B")

        result = inventory_service.get_inventory_items(search="UNIQUE-SKU")
        assert result.total == 1

    def test_category_filter(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        InventoryItemFactory(category="Seals")
        InventoryItemFactory(category="Zippers")

        result = inventory_service.get_inventory_items(category="Seals")
        assert result.total == 1
        assert result.items[0].category == "Seals"

    def test_low_stock_filter(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        InventoryItemFactory(quantity_in_stock=Decimal("2"), reorder_level=Decimal("5"))
        InventoryItemFactory(quantity_in_stock=Decimal("50"), reorder_level=Decimal("5"))

        result = inventory_service.get_inventory_items(low_stock_only=True)
        assert result.total == 1
        assert result.items[0].quantity_in_stock == Decimal("2")

    def test_is_active_filter(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        InventoryItemFactory(is_active=True, name="Active Item")
        InventoryItemFactory(is_active=False, name="Inactive Item")

        result = inventory_service.get_inventory_items(is_active=True)
        assert result.total == 1
        assert result.items[0].name == "Active Item"

    def test_excludes_soft_deleted(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        item = InventoryItemFactory()
        item.soft_delete()
        db_session.commit()

        result = inventory_service.get_inventory_items()
        assert result.total == 0

    def test_sorting(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        InventoryItemFactory(name="Zebra Part")
        InventoryItemFactory(name="Alpha Part")

        result = inventory_service.get_inventory_items(sort="name", order="asc")
        names = [i.name for i in result.items]
        assert names == ["Alpha Part", "Zebra Part"]


class TestGetInventoryItem:
    """Tests for inventory_service.get_inventory_item()."""

    def test_returns_item_by_id(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        item = InventoryItemFactory()

        result = inventory_service.get_inventory_item(item.id)
        assert result.id == item.id

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            inventory_service.get_inventory_item(9999)

    def test_raises_404_for_soft_deleted(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        item = InventoryItemFactory()
        item.soft_delete()
        db_session.commit()

        with pytest.raises(NotFound):
            inventory_service.get_inventory_item(item.id)


class TestCreateInventoryItem:
    """Tests for inventory_service.create_inventory_item()."""

    def test_creates_item(self, app, db_session):
        data = {
            "name": "Test O-Ring",
            "category": "O-Rings",
            "quantity_in_stock": 100,
            "reorder_level": 20,
        }
        item = inventory_service.create_inventory_item(data, created_by=1)
        assert item.id is not None
        assert item.name == "Test O-Ring"
        assert item.created_by == 1

    def test_defaults(self, app, db_session):
        data = {"name": "Minimal Item", "category": "Other"}
        item = inventory_service.create_inventory_item(data)
        assert item.quantity_in_stock == 0
        assert item.is_active is True


class TestUpdateInventoryItem:
    """Tests for inventory_service.update_inventory_item()."""

    def test_updates_fields(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        item = InventoryItemFactory(name="Old Name")

        result = inventory_service.update_inventory_item(
            item.id, {"name": "New Name"}
        )
        assert result.name == "New Name"

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            inventory_service.update_inventory_item(9999, {"name": "Test"})


class TestDeleteInventoryItem:
    """Tests for inventory_service.delete_inventory_item()."""

    def test_soft_deletes_item(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        item = InventoryItemFactory()

        result = inventory_service.delete_inventory_item(item.id)
        assert result.is_deleted is True

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            inventory_service.delete_inventory_item(9999)


class TestAdjustStock:
    """Tests for inventory_service.adjust_stock()."""

    def test_positive_adjustment(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        item = InventoryItemFactory(quantity_in_stock=Decimal("10"))

        result = inventory_service.adjust_stock(item.id, Decimal("5"), reason="Restock")
        assert result.quantity_in_stock == Decimal("15")

    def test_negative_adjustment(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        item = InventoryItemFactory(quantity_in_stock=Decimal("10"))

        result = inventory_service.adjust_stock(item.id, Decimal("-3"), reason="Used")
        assert result.quantity_in_stock == Decimal("7")

    def test_rejects_negative_result(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        item = InventoryItemFactory(quantity_in_stock=Decimal("5"))

        with pytest.raises(ValueError):
            inventory_service.adjust_stock(item.id, Decimal("-10"), reason="Too much")

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            inventory_service.adjust_stock(9999, Decimal("1"), reason="Test")


class TestGetLowStockItems:
    """Tests for inventory_service.get_low_stock_items()."""

    def test_returns_low_stock_items(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        InventoryItemFactory(
            quantity_in_stock=Decimal("2"),
            reorder_level=Decimal("5"),
            is_active=True,
        )
        InventoryItemFactory(
            quantity_in_stock=Decimal("50"),
            reorder_level=Decimal("5"),
            is_active=True,
        )

        results = inventory_service.get_low_stock_items()
        assert len(results) == 1

    def test_excludes_inactive(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        InventoryItemFactory(
            quantity_in_stock=Decimal("1"),
            reorder_level=Decimal("5"),
            is_active=False,
        )

        results = inventory_service.get_low_stock_items()
        assert len(results) == 0


class TestGetCategories:
    """Tests for inventory_service.get_categories()."""

    def test_returns_distinct_categories(self, app, db_session):
        InventoryItemFactory._meta.sqlalchemy_session = db_session
        InventoryItemFactory(category="Seals")
        InventoryItemFactory(category="Seals")
        InventoryItemFactory(category="Zippers")

        categories = inventory_service.get_categories()
        assert "Seals" in categories
        assert "Zippers" in categories
        assert len(categories) == 2
