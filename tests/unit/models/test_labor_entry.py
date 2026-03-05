"""Unit tests for the LaborEntry model.

Tests cover creation, the line_total property, and relationships
to order items and technicians.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.labor import LaborEntry
from tests.factories import (
    CustomerFactory,
    LaborEntryFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
    UserFactory,
)

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Configure all factories to use the given session."""
    LaborEntryFactory._meta.sqlalchemy_session = db_session
    ServiceOrderFactory._meta.sqlalchemy_session = db_session
    ServiceOrderItemFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session
    ServiceItemFactory._meta.sqlalchemy_session = db_session
    UserFactory._meta.sqlalchemy_session = db_session


class TestLaborEntryCreation:
    """Tests for basic LaborEntry creation and persistence."""

    def test_create_labor_entry(self, app, db_session):
        """A LaborEntry persists all fields correctly."""
        _set_session(db_session)
        tech = UserFactory(first_name="Tech", last_name="Worker")
        entry = LaborEntryFactory(
            tech=tech,
            hours=Decimal("2.50"),
            hourly_rate=Decimal("85.00"),
            description="Regulator overhaul",
            work_date=date(2026, 3, 1),
        )

        fetched = db_session.get(LaborEntry, entry.id)
        assert fetched is not None
        assert fetched.hours == Decimal("2.50")
        assert fetched.hourly_rate == Decimal("85.00")
        assert fetched.description == "Regulator overhaul"
        assert fetched.work_date == date(2026, 3, 1)
        assert fetched.tech_id == tech.id


class TestLaborEntryProperties:
    """Tests for computed properties."""

    def test_line_total_property(self, app, db_session):
        """line_total returns hours * hourly_rate."""
        _set_session(db_session)
        tech = UserFactory()
        entry = LaborEntryFactory(
            tech=tech,
            hours=Decimal("3.00"),
            hourly_rate=Decimal("75.00"),
        )
        assert entry.line_total == Decimal("225.00")

    def test_line_total_none_when_missing(self, app, db_session):
        """line_total returns None when hours or rate is None."""
        _set_session(db_session)
        tech = UserFactory()
        entry = LaborEntryFactory(tech=tech)
        entry.hours = None
        assert entry.line_total is None


class TestLaborEntryRelationships:
    """Tests for model relationships."""

    def test_order_item_relationship(self, app, db_session):
        """A LaborEntry links to its parent order item."""
        _set_session(db_session)
        tech = UserFactory()
        item = ServiceOrderItemFactory()
        entry = LaborEntryFactory(order_item=item, tech=tech)

        assert entry.order_item.id == item.id

    def test_tech_relationship(self, app, db_session):
        """A LaborEntry links to its technician."""
        _set_session(db_session)
        tech = UserFactory(first_name="Jane", last_name="Tech")
        entry = LaborEntryFactory(tech=tech)

        assert entry.tech.id == tech.id
        assert entry.tech.first_name == "Jane"


class TestLaborEntryRepr:
    """Tests for __repr__."""

    def test_repr(self, app, db_session):
        """__repr__ includes id, order_item_id, and tech_id."""
        _set_session(db_session)
        tech = UserFactory()
        entry = LaborEntryFactory(tech=tech)
        expected = (
            f"<LaborEntry {entry.id} item={entry.service_order_item_id} "
            f"tech={entry.tech_id}>"
        )
        assert repr(entry) == expected
