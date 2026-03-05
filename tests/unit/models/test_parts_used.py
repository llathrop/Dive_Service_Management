"""Unit tests for the PartUsed model.

Tests cover creation, the line_total property, and relationships
to order items and inventory items.
"""

from decimal import Decimal

import pytest

from app.extensions import db
from app.models.parts_used import PartUsed
from tests.factories import (
    CustomerFactory,
    InventoryItemFactory,
    PartUsedFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
)

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Configure all factories to use the given session."""
    PartUsedFactory._meta.sqlalchemy_session = db_session
    ServiceOrderFactory._meta.sqlalchemy_session = db_session
    ServiceOrderItemFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session
    ServiceItemFactory._meta.sqlalchemy_session = db_session
    InventoryItemFactory._meta.sqlalchemy_session = db_session


class TestPartUsedCreation:
    """Tests for basic PartUsed creation and persistence."""

    def test_create_part_used(self, app, db_session):
        """A PartUsed record persists all fields correctly."""
        _set_session(db_session)
        part = PartUsedFactory(
            quantity=Decimal("3.00"),
            unit_cost_at_use=Decimal("5.00"),
            unit_price_at_use=Decimal("12.50"),
            notes="Replacement seal",
        )

        fetched = db_session.get(PartUsed, part.id)
        assert fetched is not None
        assert fetched.quantity == Decimal("3.00")
        assert fetched.unit_cost_at_use == Decimal("5.00")
        assert fetched.unit_price_at_use == Decimal("12.50")
        assert fetched.notes == "Replacement seal"

    def test_defaults(self, app, db_session):
        """Default values are applied correctly."""
        _set_session(db_session)
        part = PartUsedFactory()

        assert part.is_auto_deducted is False
        assert part.applied_service_id is None


class TestPartUsedProperties:
    """Tests for computed properties."""

    def test_line_total_property(self, app, db_session):
        """line_total returns quantity * unit_price_at_use."""
        _set_session(db_session)
        part = PartUsedFactory(
            quantity=Decimal("2.00"),
            unit_price_at_use=Decimal("15.50"),
        )
        assert part.line_total == Decimal("31.00")

    def test_line_total_none_when_missing(self, app, db_session):
        """line_total returns None when quantity or price is None."""
        _set_session(db_session)
        part = PartUsedFactory()
        part.quantity = None
        assert part.line_total is None


class TestPartUsedRelationships:
    """Tests for model relationships."""

    def test_order_item_relationship(self, app, db_session):
        """A PartUsed links to its parent order item."""
        _set_session(db_session)
        item = ServiceOrderItemFactory()
        part = PartUsedFactory(order_item=item)

        assert part.order_item.id == item.id

    def test_inventory_item_relationship(self, app, db_session):
        """A PartUsed links to its inventory item."""
        _set_session(db_session)
        inv = InventoryItemFactory(name="O-Ring Kit")
        part = PartUsedFactory(inventory_item=inv)

        assert part.inventory_item.id == inv.id
        assert part.inventory_item.name == "O-Ring Kit"


class TestPartUsedRepr:
    """Tests for __repr__."""

    def test_repr(self, app, db_session):
        """__repr__ includes id, order_item_id, and inventory_item_id."""
        _set_session(db_session)
        part = PartUsedFactory()
        expected = (
            f"<PartUsed {part.id} item={part.service_order_item_id} "
            f"inv={part.inventory_item_id}>"
        )
        assert repr(part) == expected
