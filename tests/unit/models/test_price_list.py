"""Unit tests for the PriceList models.

Tests cover PriceListCategory, PriceListItem, and PriceListItemPart
creation, defaults, relationships, computed properties, and uniqueness
constraints.
"""

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.price_list import (
    PriceListCategory,
    PriceListItem,
    PriceListItemPart,
)
from tests.factories import (
    InventoryItemFactory,
    PriceListCategoryFactory,
    PriceListItemFactory,
    PriceListItemPartFactory,
)

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Configure all factories to use the given session."""
    PriceListCategoryFactory._meta.sqlalchemy_session = db_session
    PriceListItemFactory._meta.sqlalchemy_session = db_session
    PriceListItemPartFactory._meta.sqlalchemy_session = db_session
    InventoryItemFactory._meta.sqlalchemy_session = db_session


class TestPriceListCategory:
    """Tests for the PriceListCategory model."""

    def test_create_category(self, app, db_session):
        """A price list category persists with all fields."""
        _set_session(db_session)
        cat = PriceListCategoryFactory(
            name="Regulator Services",
            description="All regulator-related services",
            sort_order=1,
        )

        fetched = db_session.get(PriceListCategory, cat.id)
        assert fetched is not None
        assert fetched.name == "Regulator Services"
        assert fetched.description == "All regulator-related services"
        assert fetched.sort_order == 1
        assert fetched.is_active is True

    def test_category_unique_name(self, app, db_session):
        """Duplicate category names raise IntegrityError."""
        _set_session(db_session)
        PriceListCategoryFactory(name="Unique Cat")

        with pytest.raises(IntegrityError):
            PriceListCategoryFactory(name="Unique Cat")
            db_session.flush()

    def test_category_items_relationship(self, app, db_session):
        """Navigate from category to its items."""
        _set_session(db_session)
        cat = PriceListCategoryFactory(name="Test Nav")
        PriceListItemFactory(
            category=cat,
            name="Service A",
            price=Decimal("50.00"),
        )
        PriceListItemFactory(
            category=cat,
            name="Service B",
            price=Decimal("75.00"),
        )

        items = cat.items.all()
        assert len(items) == 2
        names = {i.name for i in items}
        assert "Service A" in names
        assert "Service B" in names


class TestPriceListItem:
    """Tests for the PriceListItem model."""

    def test_create_price_list_item(self, app, db_session):
        """A price list item persists with category FK and all fields."""
        _set_session(db_session)
        cat = PriceListCategoryFactory(name="BCD Services")
        item = PriceListItemFactory(
            category=cat,
            code="BCD-001",
            name="BCD Annual Service",
            description="Full BCD inspection and service",
            price=Decimal("85.00"),
            cost=Decimal("30.00"),
        )

        fetched = db_session.get(PriceListItem, item.id)
        assert fetched is not None
        assert fetched.code == "BCD-001"
        assert fetched.name == "BCD Annual Service"
        assert fetched.category.name == "BCD Services"
        assert float(fetched.price) == 85.00
        assert float(fetched.cost) == 30.00

    def test_price_list_item_defaults(self, app, db_session):
        """Default values are applied correctly."""
        _set_session(db_session)
        item = PriceListItemFactory(
            name="Defaults Test",
            price=Decimal("10.00"),
        )

        assert item.is_per_unit is True
        assert float(item.default_quantity) == 1.0
        assert item.unit_label == "each"
        assert item.is_taxable is True
        assert item.is_active is True

    def test_price_list_item_margin(self, app, db_session):
        """margin_percent returns correct percentage from price and cost."""
        _set_session(db_session)
        item = PriceListItemFactory(
            price=Decimal("100.00"),
            cost=Decimal("40.00"),
        )
        # Margin = ((100 - 40) / 100) * 100 = 60.0
        expected = Decimal("60.0")
        result = item.margin_percent
        assert result is not None
        assert abs(result - expected) < Decimal("0.01")

    def test_price_list_item_margin_none(self, app, db_session):
        """margin_percent returns None when cost is not set."""
        _set_session(db_session)
        item = PriceListItemFactory(
            price=Decimal("100.00"),
            cost=None,
        )
        assert item.margin_percent is None

    def test_item_unique_code(self, app, db_session):
        """Duplicate codes raise IntegrityError."""
        _set_session(db_session)
        PriceListItemFactory(code="DUP-CODE", price=Decimal("10.00"))

        with pytest.raises(IntegrityError):
            PriceListItemFactory(code="DUP-CODE", price=Decimal("20.00"))
            db_session.flush()


class TestPriceListItemPart:
    """Tests for the PriceListItemPart model."""

    def test_link_parts_to_item(self, app, db_session):
        """PriceListItemPart correctly links an item to inventory."""
        _set_session(db_session)
        inv_item = InventoryItemFactory(name="O-Ring Kit")
        pl_item = PriceListItemFactory(
            name="Reg Service",
            price=Decimal("75.00"),
            auto_deduct_parts=True,
        )
        part_link = PriceListItemPartFactory(
            price_list_item=pl_item,
            inventory_item=inv_item,
            quantity=Decimal("2"),
            notes="Use 2 per service",
        )

        fetched = db_session.get(PriceListItemPart, part_link.id)
        assert fetched is not None
        assert fetched.price_list_item.id == pl_item.id
        assert fetched.inventory_item.id == inv_item.id
        assert float(fetched.quantity) == 2.0
        assert fetched.notes == "Use 2 per service"

        # Navigate from price list item to linked parts
        parts = pl_item.linked_parts.all()
        assert len(parts) == 1
        assert parts[0].inventory_item.name == "O-Ring Kit"
