"""Unit tests for the InventoryItem model.

Tests cover creation, defaults, low-stock detection, SKU uniqueness,
soft-delete, and computed markup percentage.
"""

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.inventory import InventoryItem
from tests.factories import InventoryItemFactory

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Configure the factory to use the given session."""
    InventoryItemFactory._meta.sqlalchemy_session = db_session


class TestInventoryItemCreation:
    """Tests for basic inventory item creation."""

    def test_create_inventory_item(self, app, db_session):
        """An inventory item persists all fields correctly."""
        _set_session(db_session)
        item = InventoryItemFactory(
            sku="SEAL-001",
            name="Latex Neck Seal",
            description="Standard latex neck seal, medium",
            category="Seals",
            subcategory="Neck Seals",
            manufacturer="DUI",
            manufacturer_part_number="NS-100-M",
            purchase_cost=Decimal("12.50"),
            resale_price=Decimal("25.00"),
            markup_percent=Decimal("100.00"),
            quantity_in_stock=25,
            reorder_level=10,
            reorder_quantity=20,
            unit_of_measure="each",
            storage_location="Shelf B3",
            is_active=True,
            is_for_resale=True,
            preferred_supplier="DUI Direct",
            notes="Popular item",
        )

        fetched = db_session.get(InventoryItem, item.id)
        assert fetched is not None
        assert fetched.sku == "SEAL-001"
        assert fetched.name == "Latex Neck Seal"
        assert fetched.category == "Seals"
        assert fetched.subcategory == "Neck Seals"
        assert fetched.manufacturer == "DUI"
        assert float(fetched.purchase_cost) == 12.50
        assert float(fetched.resale_price) == 25.00
        assert fetched.quantity_in_stock == 25
        assert fetched.reorder_level == 10
        assert fetched.is_for_resale is True
        assert fetched.storage_location == "Shelf B3"


class TestInventoryDefaults:
    """Tests for default field values."""

    def test_inventory_defaults(self, app, db_session):
        """Default values are applied when fields are not specified."""
        item = InventoryItem(
            name="Test Part",
            category="General",
        )
        db_session.add(item)
        db_session.commit()

        fetched = db_session.get(InventoryItem, item.id)
        assert fetched.quantity_in_stock == 0
        assert fetched.reorder_level == 0
        assert fetched.unit_of_measure == "each"
        assert fetched.is_active is True
        assert fetched.is_for_resale is False


class TestInventoryLowStock:
    """Tests for the is_low_stock property."""

    def test_inventory_is_low_stock(self, app, db_session):
        """is_low_stock is True when qty <= reorder_level and reorder_level > 0."""
        _set_session(db_session)
        item = InventoryItemFactory(
            quantity_in_stock=3,
            reorder_level=5,
        )
        assert item.is_low_stock is True

    def test_inventory_is_low_stock_at_level(self, app, db_session):
        """is_low_stock is True when qty equals reorder_level."""
        _set_session(db_session)
        item = InventoryItemFactory(
            quantity_in_stock=5,
            reorder_level=5,
        )
        assert item.is_low_stock is True

    def test_inventory_not_low_stock_above_level(self, app, db_session):
        """is_low_stock is False when qty > reorder_level."""
        _set_session(db_session)
        item = InventoryItemFactory(
            quantity_in_stock=10,
            reorder_level=5,
        )
        assert item.is_low_stock is False

    def test_inventory_not_low_stock_zero_reorder(self, app, db_session):
        """is_low_stock is False when reorder_level is 0 (no reorder configured)."""
        _set_session(db_session)
        item = InventoryItemFactory(
            quantity_in_stock=0,
            reorder_level=0,
        )
        assert item.is_low_stock is False


class TestInventorySkuUniqueness:
    """Tests for SKU uniqueness constraint."""

    def test_inventory_unique_sku(self, app, db_session):
        """Inserting a duplicate SKU raises IntegrityError."""
        _set_session(db_session)
        InventoryItemFactory(sku="DUP-SKU")

        with pytest.raises(IntegrityError):
            InventoryItemFactory(sku="DUP-SKU")
            db_session.flush()


class TestInventorySoftDelete:
    """Tests for soft-delete support."""

    def test_inventory_soft_delete(self, app, db_session):
        """soft_delete() flags the item and not_deleted() excludes it."""
        _set_session(db_session)
        item = InventoryItemFactory()
        item.soft_delete()
        db_session.commit()

        fetched = db_session.get(InventoryItem, item.id)
        assert fetched.is_deleted is True
        assert fetched.deleted_at is not None

        active = InventoryItem.not_deleted().all()
        assert item.id not in [i.id for i in active]


class TestInventoryMarkup:
    """Tests for the computed_markup_percent property."""

    def test_inventory_margin(self, app, db_session):
        """computed_markup_percent returns correct percentage."""
        _set_session(db_session)
        item = InventoryItemFactory(
            purchase_cost=Decimal("10.00"),
            resale_price=Decimal("25.00"),
        )
        # Markup = ((25 - 10) / 10) * 100 = 150.0
        expected = Decimal("150.0")
        result = item.computed_markup_percent
        assert result is not None
        assert abs(result - expected) < Decimal("0.01")

    def test_inventory_margin_none_when_no_cost(self, app, db_session):
        """computed_markup_percent returns None when purchase_cost is missing."""
        _set_session(db_session)
        item = InventoryItemFactory(
            purchase_cost=None,
            resale_price=Decimal("25.00"),
        )
        assert item.computed_markup_percent is None

    def test_inventory_margin_none_when_zero_cost(self, app, db_session):
        """computed_markup_percent returns None when purchase_cost is zero."""
        _set_session(db_session)
        item = InventoryItemFactory(
            purchase_cost=Decimal("0.00"),
            resale_price=Decimal("25.00"),
        )
        assert item.computed_markup_percent is None
