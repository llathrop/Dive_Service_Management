"""Unit tests for the price list service layer.

Tests cover category and item CRUD, item duplication, and part linking.
"""

from decimal import Decimal

import pytest

from app.extensions import db
from app.models.inventory import InventoryItem
from app.models.price_list import (
    PriceListCategory,
    PriceListItem,
    PriceListItemPart,
)
from app.services import price_list_service

pytestmark = pytest.mark.unit


def _make_category(db_session, **kwargs):
    """Create and persist a PriceListCategory with sensible defaults."""
    defaults = {
        "name": "Test Category",
        "sort_order": 0,
        "is_active": True,
    }
    defaults.update(kwargs)
    category = PriceListCategory(**defaults)
    db_session.add(category)
    db_session.commit()
    return category


def _make_price_list_item(db_session, category, **kwargs):
    """Create and persist a PriceListItem with sensible defaults."""
    defaults = {
        "category_id": category.id,
        "name": "Test Service",
        "price": Decimal("50.00"),
        "is_active": True,
    }
    defaults.update(kwargs)
    item = PriceListItem(**defaults)
    db_session.add(item)
    db_session.commit()
    return item


def _make_inventory_item(db_session, **kwargs):
    """Create and persist an InventoryItem with sensible defaults."""
    defaults = {
        "name": "Test Part",
        "category": "General",
        "quantity_in_stock": 10,
    }
    defaults.update(kwargs)
    item = InventoryItem(**defaults)
    db_session.add(item)
    db_session.commit()
    return item


class TestGetCategories:
    """Tests for get_categories()."""

    def test_get_categories(self, app, db_session):
        """Returns categories ordered by sort_order."""
        _make_category(db_session, name="Zippers", sort_order=2)
        _make_category(db_session, name="Regulators", sort_order=1)
        _make_category(db_session, name="Seals", sort_order=0)

        categories = price_list_service.get_categories(active_only=False)
        names = [c.name for c in categories]
        assert names == ["Seals", "Regulators", "Zippers"]

    def test_get_categories_active_only(self, app, db_session):
        """active_only=True excludes inactive categories."""
        _make_category(db_session, name="Active", is_active=True)
        _make_category(db_session, name="Inactive", is_active=False)

        categories = price_list_service.get_categories(active_only=True)
        names = [c.name for c in categories]
        assert "Active" in names
        assert "Inactive" not in names


class TestCreateCategory:
    """Tests for create_category()."""

    def test_create_category(self, app, db_session):
        """create_category() persists a category with provided fields."""
        data = {
            "name": "New Category",
            "description": "A test category",
            "sort_order": 5,
        }
        category = price_list_service.create_category(data)

        assert category.id is not None
        assert category.name == "New Category"
        assert category.description == "A test category"
        assert category.sort_order == 5


class TestUpdateCategory:
    """Tests for update_category()."""

    def test_update_category(self, app, db_session):
        """update_category() updates fields correctly."""
        category = _make_category(db_session, name="Old Name")

        updated = price_list_service.update_category(
            category.id, {"name": "New Name", "description": "Updated"}
        )

        assert updated.name == "New Name"
        assert updated.description == "Updated"


class TestGetPriceListItems:
    """Tests for get_price_list_items()."""

    def test_get_price_list_items(self, app, db_session):
        """Returns all active price list items."""
        cat = _make_category(db_session, name="Services")
        _make_price_list_item(db_session, cat, name="Service A")
        _make_price_list_item(db_session, cat, name="Service B")

        items = price_list_service.get_price_list_items()
        assert len(items) == 2

    def test_get_price_list_items_by_category(self, app, db_session):
        """Filtering by category_id returns only items in that category."""
        cat1 = _make_category(db_session, name="Cat 1")
        cat2 = _make_category(db_session, name="Cat 2")
        _make_price_list_item(db_session, cat1, name="In Cat 1")
        _make_price_list_item(db_session, cat2, name="In Cat 2")

        items = price_list_service.get_price_list_items(category_id=cat1.id)
        assert len(items) == 1
        assert items[0].name == "In Cat 1"


class TestCreatePriceListItem:
    """Tests for create_price_list_item()."""

    def test_create_price_list_item(self, app, db_session):
        """create_price_list_item() persists an item with all fields."""
        cat = _make_category(db_session, name="Services")
        data = {
            "category_id": cat.id,
            "name": "Regulator Service",
            "code": "REG-SVC-001",
            "price": Decimal("75.00"),
            "cost": Decimal("25.00"),
            "description": "Full regulator service",
        }
        item = price_list_service.create_price_list_item(data)

        assert item.id is not None
        assert item.name == "Regulator Service"
        assert item.code == "REG-SVC-001"
        assert float(item.price) == 75.00


class TestUpdatePriceListItem:
    """Tests for update_price_list_item()."""

    def test_update_price_list_item(self, app, db_session):
        """update_price_list_item() updates fields correctly."""
        cat = _make_category(db_session, name="Services")
        item = _make_price_list_item(db_session, cat, name="Old Service")

        updated = price_list_service.update_price_list_item(
            item.id,
            {"name": "New Service", "price": Decimal("100.00")},
        )

        assert updated.name == "New Service"
        assert float(updated.price) == 100.00


class TestDuplicatePriceListItem:
    """Tests for duplicate_price_list_item()."""

    def test_duplicate_price_list_item(self, app, db_session):
        """Duplicate has ' (Copy)' in name and cleared code."""
        cat = _make_category(db_session, name="Services")
        original = _make_price_list_item(
            db_session,
            cat,
            name="Original Service",
            code="SVC-001",
            price=Decimal("50.00"),
            description="Original description",
        )

        duplicate = price_list_service.duplicate_price_list_item(original.id)

        assert duplicate.id != original.id
        assert duplicate.name == "Original Service (Copy)"
        assert duplicate.code is None
        assert float(duplicate.price) == 50.00
        assert duplicate.description == "Original description"
        assert duplicate.category_id == original.category_id


class TestLinkPart:
    """Tests for link_part()."""

    def test_link_part(self, app, db_session):
        """link_part() creates a PriceListItemPart association."""
        cat = _make_category(db_session, name="Services")
        pli = _make_price_list_item(db_session, cat, name="Service A")
        inv = _make_inventory_item(db_session, name="O-Ring")

        link = price_list_service.link_part(
            pli.id, inv.id, quantity=2, notes="Required part"
        )

        assert link.id is not None
        assert link.price_list_item_id == pli.id
        assert link.inventory_item_id == inv.id
        assert float(link.quantity) == 2.0
        assert link.notes == "Required part"


class TestUnlinkPart:
    """Tests for unlink_part()."""

    def test_unlink_part(self, app, db_session):
        """unlink_part() deletes the PriceListItemPart link."""
        cat = _make_category(db_session, name="Services")
        pli = _make_price_list_item(db_session, cat, name="Service A")
        inv = _make_inventory_item(db_session, name="O-Ring")

        link = PriceListItemPart(
            price_list_item_id=pli.id,
            inventory_item_id=inv.id,
            quantity=1,
        )
        db_session.add(link)
        db_session.commit()
        link_id = link.id

        price_list_service.unlink_part(link_id)

        assert db_session.get(PriceListItemPart, link_id) is None
